"""
Business report tool module.

Contains the business_report MCP tool and all its helper functions.
"""

import json
import datetime
from typing import List, Dict
from config import ODOO_DB, ODOO_PASSWORD, ODOO_URL, STAGE_IDS, CATEGORY_IDS
from services.odoo_client import get_odoo_connection
from services.formatters import format_currency, strip_html_tags
from services.ai import generate_top5_ai_summary


# The mcp instance will be injected by the main module
mcp = None


def init_mcp(mcp_instance):
    """Initialize the mcp instance for this module"""
    global mcp
    mcp = mcp_instance
    
    # Register the tool
    mcp.tool()(odoo_business_report)


# Import odoo_search and odoo_execute from data module (to avoid circular import)
# This will be available after main module initializes everything
def odoo_search(*args, **kwargs):
    """Wrapper to call odoo_search from tools.data"""
    from tools.data import odoo_search as _odoo_search
    return _odoo_search(*args, **kwargs)


def odoo_execute(*args, **kwargs):
    """Wrapper to call odoo_execute from tools.data"""
    from tools.data import odoo_execute as _odoo_execute
    return _odoo_execute(*args, **kwargs)


def odoo_business_report(
    user_ids: List[int],  # CHANGÉ: maintenant une liste
    start_date: str, 
    end_date: str,
    project_id: int,
    task_column_id: int
) -> str:
    """
    Generate a comprehensive business report for multiple users over a specified period.
    Collects revenue, metrics, and top clients data from Odoo and creates a task with the report.
    
    Args:
        user_ids: List of IDs of Odoo users/salespersons to generate report for
        start_date: Start date in ISO format (YYYY-MM-DD)
        end_date: End date in ISO format (YYYY-MM-DD)
        project_id: ID of the project where the report task will be created
        task_column_id: ID of the task column/stage where the report will be placed
    
    Returns:
        JSON string with the complete business report data
    """
    try:
        # Validate input
        if not user_ids or not isinstance(user_ids, list):
            return json.dumps({
                "status": "error",
                "message": "user_ids must be a non-empty list"
            })
        
        # Validate date format
        try:
            datetime.datetime.fromisoformat(start_date)
            datetime.datetime.fromisoformat(end_date)
        except ValueError:
            return json.dumps({
                "status": "error",
                "message": "Invalid date format. Use YYYY-MM-DD format."
            })
        
        # Validate that start_date is before end_date
        if start_date >= end_date:
            return json.dumps({
                "status": "error", 
                "message": "start_date must be before end_date"
            })
        
        # Test Odoo connection first
        models, uid = get_odoo_connection()
        
        # Verify ALL users exist and get their names
        user_names = []
        for user_id in user_ids:
            user_check = odoo_search(
                model='res.users',
                domain=[['id', '=', user_id]],
                fields=['name'],
                limit=1
            )
            user_response = json.loads(user_check)
            if not (user_response.get('status') == 'success' and user_response.get('records')):
                return json.dumps({
                    "status": "error",
                    "message": f"User with ID {user_id} not found"
                })
            user_names.append(user_response['records'][0]['name'])
        
        # Create combined user info
        combined_user_name = ", ".join(user_names)
        
        # Collect all report data (AGRÉGÉ pour tous les utilisateurs)
        top_clients_data = collect_top_clients_data(user_ids)

        # Collecter les activités des Top 5 clients
        top5_activities = collect_top5_client_activities(start_date, end_date, top_clients_data)

        # Générer les résumés AI pour chaque Top 5
        top5_summaries = {}
        for top_key in ['top_1', 'top_2', 'top_3', 'top_4', 'top_5']:
            client_activities = top5_activities.get(top_key)
            if client_activities:
                summary = generate_top5_ai_summary(client_activities, start_date, end_date)
                top5_summaries[top_key] = summary
            else:
                top5_summaries[top_key] = "Aucun client"

        report_data = {
            "user_info": {
                "user_ids": user_ids,
                "user_names": user_names,
                "combined_user_name": combined_user_name,
                "start_date": start_date,
                "end_date": end_date
            },
            "revenue_data": collect_revenue_data(start_date, end_date, user_ids),
            "metrics_data": collect_metrics_data(start_date, end_date, user_ids),
            "top_clients_data": top_clients_data,
            "top5_summaries": top5_summaries  # NOUVEAU: résumés AI des Top 5
        }

        # Create task with formatted report
        task_id = create_report_task(report_data, project_id, task_column_id)

        return json.dumps({
            "status": "success",
            "message": f"Business report generated successfully for {combined_user_name}",
            "period": f"{start_date} to {end_date}",
            "task_id": task_id,
            "task_name": f"Rapport Business - {combined_user_name} ({start_date} au {end_date})",
            "report_data": report_data,
            "timestamp": datetime.datetime.now().isoformat()
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Error generating business report: {str(e)}"
        })


# Business report helper functions

def get_company_name(company_id: int):
    """
    Get company name by ID for dynamic labeling
    
    Args:
        company_id: ID of the company
    
    Returns:
        Company name or fallback string
    """
    try:
        result = odoo_search(
            model='res.company',
            domain=[['id', '=', company_id]],
            fields=['name'],
            limit=1
        )
        
        response = json.loads(result)
        if response.get('status') == 'success' and response.get('records'):
            # Clean name for use as key (remove accents, spaces, etc.)
            name = response['records'][0]['name']
            return name.lower().replace('é', 'e').replace(' ', '_')
        return f"company_{company_id}"
        
    except Exception as e:
        return f"company_{company_id}"

def get_company_revenue(company_id: int, start_date: str, end_date: str, user_id: int, with_opportunities=None):
    """
    Generic function to get company revenue based on opportunities filter
    
    Args:
        company_id: ID of the company
        start_date: Start date in ISO format
        end_date: End date in ISO format  
        user_id: ID of the user/salesperson
        with_opportunities: True for invoices WITH opportunities, False for WITHOUT, None for ALL
    
    Returns:
        Total revenue amount
    """
    try:
        # Build domain for account.move (invoices)
        domain = [
            ['company_id', '=', company_id],
            ['invoice_date', '>=', start_date],
            ['invoice_date', '<=', end_date],
            ['invoice_user_id', '=', user_id],
            ['move_type', '=', 'out_invoice'],  # Only customer invoices
            ['state', '=', 'posted']  # Only validated invoices
        ]
        
        # Add opportunities filter
        if with_opportunities is True:
            # For invoices with opportunities - check if related sale order has opportunity
            domain.append(['invoice_line_ids.sale_line_ids.order_id.opportunity_id', '!=', False])
        elif with_opportunities is False:
            # For invoices without opportunities - check if related sale order has NO opportunity
            domain.append(['invoice_line_ids.sale_line_ids.order_id.opportunity_id', '=', False])
        # If None, no opportunity filter (total)
        
        # Search invoices
        result = odoo_search(
            model='account.move',
            domain=domain,
            fields=['amount_total'],
            limit=100  # Should be enough for weekly reports
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            records = response.get('records', [])
            total_revenue = sum(record.get('amount_total', 0) for record in records)
            return total_revenue
        else:
            raise Exception(f"Search failed: {response.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise Exception(f"Error calculating revenue: {str(e)}")


def get_company_invoices_revenue(
    company_id: int,
    start_date: str,
    end_date: str,
    user_ids: List[int],
    with_opportunities=None
):
    """
    Fonction pour calculer le CA facturé HT (account.move) basé sur les opportunités
    MODIFIÉ pour supporter plusieurs utilisateurs et CA HT
    """
    try:
        # Build domain for account.move (invoices)
        domain = [
            ['company_id', '=', company_id],
            ['invoice_date', '>=', start_date],
            ['invoice_date', '<=', end_date],
            ['invoice_user_id', 'in', user_ids],
            ['move_type', '=', 'out_invoice'],
            ['state', '=', 'posted']
        ]

        # Add opportunities filter
        if with_opportunities is True:
            domain.append([
                'invoice_line_ids.sale_line_ids.order_id.opportunity_id',
                '!=',
                False
            ])
        elif with_opportunities is False:
            domain.append([
                'invoice_line_ids.sale_line_ids.order_id.opportunity_id',
                '=',
                False
            ])

        # Search invoices
        result = odoo_search(
            model='account.move',
            domain=domain,
            fields=['amount_untaxed'],
            limit=100
        )

        response = json.loads(result)
        if response.get('status') == 'success':
            records = response.get('records', [])
            total_revenue = sum(
                record.get('amount_untaxed', 0) for record in records
            )
            return total_revenue
        else:
            raise Exception(
                f"Search failed: {response.get('error', 'Unknown error')}"
            )

    except Exception as e:
        raise Exception(f"Error calculating invoiced revenue: {str(e)}")


def get_company_invoices_revenue_by_trademark(
    company_id: int,
    start_date: str,
    end_date: str,
    user_ids: List[int],
    with_opportunities=None
):
    """
    Fonction pour calculer le CA facturé HT par marque commerciale

    Args:
        company_id: ID de la société
        start_date: Date de début
        end_date: Date de fin
        user_ids: Liste des IDs utilisateurs
        with_opportunities: Filtre opportunités (True/False/None)

    Returns:
        Dict avec les montants par marque: {"La Balle": 3000, "Sans marque": 500, ...}
    """
    try:
        # Build domain for account.move (invoices)
        domain = [
            ['company_id', '=', company_id],
            ['invoice_date', '>=', start_date],
            ['invoice_date', '<=', end_date],
            ['invoice_user_id', 'in', user_ids],
            ['move_type', '=', 'out_invoice'],
            ['state', '=', 'posted']
        ]

        # Add opportunities filter
        if with_opportunities is True:
            domain.append([
                'invoice_line_ids.sale_line_ids.order_id.opportunity_id',
                '!=',
                False
            ])
        elif with_opportunities is False:
            domain.append([
                'invoice_line_ids.sale_line_ids.order_id.opportunity_id',
                '=',
                False
            ])

        # Search invoices with invoice_line_ids
        result = odoo_search(
            model='account.move',
            domain=domain,
            fields=['id', 'invoice_line_ids'],
            limit=100
        )

        response = json.loads(result)
        if response.get('status') != 'success':
            raise Exception(
                f"Search failed: {response.get('error', 'Unknown error')}"
            )

        invoices = response.get('records', [])
        trademark_totals = {}

        # Pour chaque facture, récupérer les lignes
        for invoice in invoices:
            line_ids = invoice.get('invoice_line_ids', [])

            if not line_ids:
                continue

            # Récupérer les lignes de facture avec product_id et price_subtotal
            lines_result = odoo_search(
                model='account.move.line',
                domain=[['id', 'in', line_ids]],
                fields=['product_id', 'price_subtotal'],
                limit=1000
            )

            lines_response = json.loads(lines_result)
            if lines_response.get('status') != 'success':
                continue

            lines = lines_response.get('records', [])

            for line in lines:
                product_id = line.get('product_id')
                price_subtotal = line.get('price_subtotal', 0)

                if not product_id or not isinstance(product_id, list):
                    # Pas de produit, catégoriser comme "Sans marque"
                    trademark = "Sans marque"
                else:
                    # Récupérer le champ products_trademark du produit
                    product_result = odoo_search(
                        model='product.product',
                        domain=[['id', '=', product_id[0]]],
                        fields=['products_trademark'],
                        limit=1
                    )

                    product_response = json.loads(product_result)
                    if (product_response.get('status') == 'success' and
                        product_response.get('records')):
                        trademark = product_response['records'][0].get('products_trademark')
                        if not trademark or trademark.strip() == '':
                            trademark = "Sans marque"
                    else:
                        trademark = "Sans marque"

                # Ajouter au total de la marque
                if trademark not in trademark_totals:
                    trademark_totals[trademark] = 0
                trademark_totals[trademark] += price_subtotal

        return trademark_totals

    except Exception as e:
        raise Exception(f"Error calculating revenue by trademark: {str(e)}")


def collect_revenue_data(start_date: str, end_date: str, user_ids: List[int]):
    """
    Collect all revenue data for the business report using dynamic company detection
    REFACTORISÉ pour générer CA individuel par commercial + totaux par société + détails par marque
    """
    try:
        # Get ALL company IDs for ALL users
        all_company_ids = set()

        for user_id in user_ids:
            result = odoo_search(
                model='res.users',
                domain=[['id', '=', user_id]],
                fields=['company_ids'],
                limit=1
            )

            response = json.loads(result)
            if (response.get('status') == 'success'
                    and response.get('records')):
                company_ids = response['records'][0].get('company_ids', [])
                all_company_ids.update(company_ids)

        if not all_company_ids:
            raise Exception(
                f"Users {user_ids} have no associated companies"
            )

        # Calculate revenue for each company
        revenue_data = {}
        # NOUVEAU: Stocker les détails par marque
        trademark_details = {}

        for company_id in all_company_ids:
            company_key = get_company_name(company_id)
            company_total = 0

            # CA individuel pour chaque commercial
            for user_id in user_ids:
                individual_ca = get_company_invoices_revenue(
                    company_id, start_date, end_date, [user_id],
                    with_opportunities=None
                )
                key = f"ca_facture_{company_key}_commercial_{user_id}"
                revenue_data[key] = individual_ca
                company_total += individual_ca

                # NOUVEAU: Récupérer le détail par marque pour ce commercial et cette société
                trademark_breakdown = get_company_invoices_revenue_by_trademark(
                    company_id, start_date, end_date, [user_id],
                    with_opportunities=None
                )
                trademark_key = f"ca_facture_{company_key}_commercial_{user_id}_trademarks"
                trademark_details[trademark_key] = trademark_breakdown

            # CA total pour la société
            revenue_data[f"ca_facture_{company_key}_total"] = company_total

        # Ajouter les détails de marque dans le retour
        revenue_data['trademark_details'] = trademark_details

        return revenue_data

    except Exception as e:
        raise Exception(f"Error collecting revenue data: {str(e)}")


def get_appointments_placed(start_date: str, end_date: str, user_ids: List[int]):
    """MODIFIÉ pour supporter plusieurs utilisateurs"""
    try:
        result = odoo_search(
            model='crm.lead',
            domain=[
                ['create_date', '>=', start_date],
                ['create_date', '<=', end_date],
                ['user_id', 'in', user_ids],  # CHANGÉ: 'in' au lieu de '='
                ['stage_id', '=', STAGE_IDS["rdv_degustation"]]
            ],
            fields=['id']
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            return response.get('returned_count', 0)
        else:
            raise Exception(f"Search failed: {response.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise Exception(f"Error getting appointments placed: {str(e)}")


def check_field_exists(model: str, field_name: str) -> bool:
    """
    Vérifie si un champ existe sur un modèle Odoo
    Utile pour les champs Studio qui peuvent être supprimés

    Args:
        model: Nom du modèle Odoo (ex: 'wine.price.survey')
        field_name: Nom du champ à vérifier (ex: 'x_studio_is_meeting')

    Returns:
        True si le champ existe, False sinon
    """
    try:
        result = odoo_execute(
            model='ir.model.fields',
            method='search_count',
            args=[[
                ['model', '=', model],
                ['name', '=', field_name]
            ]]
        )

        response = json.loads(result)
        if response.get('status') == 'success':
            return response.get('result', 0) > 0
        else:
            return False

    except Exception as e:
        print(f"[WARNING] Could not check field existence for {model}.{field_name}: {str(e)}")
        return False


def get_passer_voir_count(start_date: str, end_date: str, user_ids: List[int]):
    """
    MODIFIÉ pour supporter plusieurs utilisateurs ET inclure les visites GD
    Compte à la fois:
    - Les crm.lead avec stage "passer_voir" (commerciaux CHR)
    - Les wine.price.survey sans rendez-vous (commerciaux GD)

    Avec protection: si le champ Studio n'existe plus, seuls les CHR sont comptés
    """
    try:
        # Compter les crm.lead "passer_voir" (CHR)
        result_chr = odoo_execute(
            model='crm.lead',
            method='search_count',
            args=[[
                ['create_date', '>=', start_date],
                ['create_date', '<=', end_date],
                ['user_id', 'in', user_ids],
                ['stage_id', '=', STAGE_IDS["passer_voir"]]
            ]]
        )

        response_chr = json.loads(result_chr)
        if response_chr.get('status') == 'success':
            chr_count = response_chr.get('result', 0)
        else:
            raise Exception(f"CHR search failed: {response_chr.get('error', 'Unknown error')}")

        # Compter les wine.price.survey sans rendez-vous (GD visites)
        # Cette fonction retourne 0 si le champ n'existe plus
        gd_count = get_gd_visits_count(start_date, end_date, user_ids)

        # Retourner le total
        return chr_count + gd_count

    except Exception as e:
        raise Exception(f"Error getting Passer Voir count: {str(e)}")


def get_gd_visits_count(start_date: str, end_date: str, user_ids: List[int]):
    """
    Compte les visites GD (wine.price.survey sans rendez-vous)
    Avec protection contre la suppression du champ Studio x_studio_is_meeting

    Args:
        start_date: Date de début au format YYYY-MM-DD
        end_date: Date de fin au format YYYY-MM-DD
        user_ids: Liste des IDs utilisateurs

    Returns:
        Nombre de visites GD (wine.price.survey où x_studio_is_meeting = False ou absent)
        Retourne 0 si le champ n'existe plus ou en cas d'erreur
    """
    try:
        # Vérifier si le champ x_studio_is_meeting existe
        field_exists = check_field_exists('wine.price.survey', 'x_studio_is_meeting')

        if not field_exists:
            print("[WARNING] Field x_studio_is_meeting does not exist on wine.price.survey, skipping GD visits count")
            return 0

        # Extraire uniquement la partie date (YYYY-MM-DD) sans l'heure
        # survey_date est un champ Date, pas DateTime
        start_date_only = start_date.split('T')[0].split(' ')[0]
        end_date_only = end_date.split('T')[0].split(' ')[0]

        # Le champ existe, procéder normalement
        # Compter tous les wine.price.survey SANS x_studio_is_meeting = True
        # Note: On utilise != True au lieu de = False | = None car XML-RPC ne peut pas marshaller None
        result = odoo_execute(
            model='wine.price.survey',
            method='search_count',
            args=[[
                ['survey_date', '>=', start_date_only],
                ['survey_date', '<=', end_date_only],
                ['user_id', 'in', user_ids],
                ['x_studio_is_meeting', '!=', True]
            ]]
        )

        response = json.loads(result)
        if response.get('status') == 'success':
            return response.get('result', 0)
        else:
            print(f"[WARNING] GD visits search failed: {response.get('error', 'Unknown error')}")
            return 0

    except Exception as e:
        print(f"[WARNING] Error getting GD visits count: {str(e)}")
        return 0


def get_gd_meetings_count(start_date: str, end_date: str, user_ids: List[int]):
    """
    Compte les rendez-vous GD (wine.price.survey avec x_studio_is_meeting = True)
    Avec protection contre la suppression du champ Studio x_studio_is_meeting

    Args:
        start_date: Date de début au format YYYY-MM-DD
        end_date: Date de fin au format YYYY-MM-DD
        user_ids: Liste des IDs utilisateurs

    Returns:
        Nombre de rendez-vous GD (wine.price.survey où x_studio_is_meeting = True)
        Retourne 0 si le champ n'existe plus ou en cas d'erreur
    """
    try:
        # Vérifier si le champ x_studio_is_meeting existe
        field_exists = check_field_exists('wine.price.survey', 'x_studio_is_meeting')

        if not field_exists:
            print("[WARNING] Field x_studio_is_meeting does not exist on wine.price.survey, skipping GD meetings count")
            return 0

        # Extraire uniquement la partie date (YYYY-MM-DD) sans l'heure
        # survey_date est un champ Date, pas DateTime
        start_date_only = start_date.split('T')[0].split(' ')[0]
        end_date_only = end_date.split('T')[0].split(' ')[0]

        # Le champ existe, procéder normalement
        result = odoo_execute(
            model='wine.price.survey',
            method='search_count',
            args=[[
                ['survey_date', '>=', start_date_only],
                ['survey_date', '<=', end_date_only],
                ['user_id', 'in', user_ids],
                ['x_studio_is_meeting', '=', True]
            ]]
        )

        response = json.loads(result)
        if response.get('status') == 'success':
            return response.get('result', 0)
        else:
            print(f"[WARNING] GD meetings search failed: {response.get('error', 'Unknown error')}")
            return 0

    except Exception as e:
        print(f"[WARNING] Error getting GD meetings count: {str(e)}")
        return 0


def get_appointments_realized(start_date: str, end_date: str, user_ids: List[int]):
    """
    MODIFIÉ pour supporter plusieurs utilisateurs ET inclure les rendez-vous GD
    Compte à la fois:
    - Les wine.tasting (commerciaux CHR)
    - Les wine.price.survey avec x_studio_is_meeting=True (commerciaux GD)

    Avec protection: si le champ Studio n'existe plus, seuls les CHR sont comptés
    """
    try:
        # Compter les wine.tasting (CHR)
        result_chr = odoo_execute(
            model='wine.tasting',
            method='search_count',
            args=[[
                ['create_date', '>=', start_date],
                ['create_date', '<=', end_date],
                ['opportunity_id.user_id', 'in', user_ids]
            ]]
        )

        response_chr = json.loads(result_chr)
        if response_chr.get('status') == 'success':
            chr_count = response_chr.get('result', 0)
        else:
            raise Exception(f"CHR search failed: {response_chr.get('error', 'Unknown error')}")

        # Compter les wine.price.survey avec rendez-vous (GD)
        # Cette fonction retourne 0 si le champ n'existe plus
        gd_count = get_gd_meetings_count(start_date, end_date, user_ids)

        # Retourner le total
        return chr_count + gd_count

    except Exception as e:
        raise Exception(f"Error getting appointments realized: {str(e)}")


def get_orders_count(start_date: str, end_date: str, user_ids: List[int]):
    """MODIFIÉ pour supporter plusieurs utilisateurs"""
    try:
        result = odoo_search(
            model='sale.order',
            domain=[
                ['date_order', '>=', start_date],
                ['date_order', '<=', end_date],
                ['user_id', 'in', user_ids]  # CHANGÉ
            ],
            fields=['id']
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            return response.get('returned_count', 0)
        else:
            raise Exception(f"Search failed: {response.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise Exception(f"Error getting orders count: {str(e)}")

def get_recommendations_count(start_date: str, end_date: str, user_ids: List[int]):
    """MODIFIÉ pour supporter plusieurs utilisateurs"""
    try:
        result = odoo_search(
            model='res.partner',
            domain=[
                ['user_id', 'in', user_ids],  # CHANGÉ
                ['create_date', '>=', start_date],
                ['create_date', '<=', end_date],
                ['category_id', 'in', [CATEGORY_IDS["recommandation"]]]
            ],
            fields=['id']
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            return response.get('returned_count', 0)
        else:
            raise Exception(f"Search failed: {response.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise Exception(f"Error getting recommendations count: {str(e)}")


def get_deliveries_count(start_date: str, end_date: str, user_ids: List[int]):
    """MODIFIÉ pour supporter plusieurs utilisateurs et filtrer uniquement les livraisons sortantes"""
    try:
        result = odoo_execute(
            model='stock.picking',
            method='search_count',
            args=[[
                ['date_done', '>=', start_date],
                ['date_done', '<=', end_date],
                ['user_id', 'in', user_ids],
                ['picking_type_code', '=', 'outgoing']  # Uniquement les livraisons clients
            ]]
        )

        response = json.loads(result)
        if response.get('status') == 'success':
            return response.get('result', 0)
        else:
            raise Exception(f"Search failed: {response.get('error', 'Unknown error')}")

    except Exception as e:
        raise Exception(f"Error getting deliveries count: {str(e)}")


def get_payment_reminders_count(start_date: str, end_date: str, user_ids: List[int]):
    """
    Compte les activités de recouvrement (relances impayées) terminées pour plusieurs utilisateurs

    Args:
        start_date: Date de début au format YYYY-MM-DD
        end_date: Date de fin au format YYYY-MM-DD
        user_ids: Liste des IDs utilisateurs

    Returns:
        Nombre total d'activités de recouvrement terminées
    """
    try:
        result = odoo_execute(
            model='mail.activity',
            method='search_count',
            args=[[
                ['activity_type_id', '=', 123],  # Type "Recouvrement"
                ['user_id', 'in', user_ids],
                ['date_done', '>=', start_date],
                ['date_done', '<=', end_date],
                ['state', '=', 'done']
            ]]
        )

        response = json.loads(result)
        if response.get('status') == 'success':
            return response.get('result', 0)
        else:
            raise Exception(f"Search failed: {response.get('error', 'Unknown error')}")

    except Exception as e:
        raise Exception(f"Error getting payment reminders count: {str(e)}")


def get_payment_reminders_count_individual(start_date: str, end_date: str, user_ids: List[int]):
    """
    Compte les activités de recouvrement individuellement pour chaque utilisateur

    Args:
        start_date: Date de début au format YYYY-MM-DD
        end_date: Date de fin au format YYYY-MM-DD
        user_ids: Liste des IDs utilisateurs

    Returns:
        Dict avec user_id comme clé et le nombre de relances comme valeur
    """
    try:
        individual_counts = {}

        for user_id in user_ids:
            result = odoo_execute(
                model='mail.activity',
                method='search_count',
                args=[[
                    ['activity_type_id', '=', 123],  # Type "Recouvrement"
                    ['user_id', '=', user_id],
                    ['date_done', '>=', start_date],
                    ['date_done', '<=', end_date],
                    ['state', '=', 'done']
                ]]
            )

            response = json.loads(result)
            if response.get('status') == 'success':
                individual_counts[user_id] = response.get('result', 0)
            else:
                individual_counts[user_id] = 0

        return individual_counts

    except Exception as e:
        raise Exception(f"Error getting individual payment reminders count: {str(e)}")


def get_appointments_placed_individual(start_date: str, end_date: str, user_ids: List[int]):
    """Get appointments placed count for each user individually"""
    try:
        individual_counts = {}

        for user_id in user_ids:
            result = odoo_execute(
                model='crm.lead',
                method='search_count',
                args=[[
                    ['create_date', '>=', start_date],
                    ['create_date', '<=', end_date],
                    ['user_id', '=', user_id],
                    ['stage_id', '=', STAGE_IDS["rdv_degustation"]]
                ]]
            )

            response = json.loads(result)
            if response.get('status') == 'success':
                individual_counts[user_id] = response.get('result', 0)
            else:
                individual_counts[user_id] = 0

        return individual_counts

    except Exception as e:
        raise Exception(f"Error getting individual appointments placed: {str(e)}")


def get_orders_count_individual(
        start_date: str,
        end_date: str,
        user_ids: List[int]
        ):
    """Get orders count for each user individually"""
    try:
        individual_counts = {}

        for user_id in user_ids:
            result = odoo_execute(
                model='sale.order',
                method='search_count',
                args=[[
                    ['date_order', '>=', start_date],
                    ['date_order', '<=', end_date],
                    ['user_id', '=', user_id]
                ]]
            )

            response = json.loads(result)
            if response.get('status') == 'success':
                individual_counts[user_id] = response.get('result', 0)
            else:
                individual_counts[user_id] = 0

        return individual_counts

    except Exception as e:
        raise Exception(f"Error getting individual orders count: {str(e)}")


def get_recommendations_count_individual(start_date: str, end_date: str, user_ids: List[int]):
    """Get recommendations count for each user individually"""
    try:
        individual_counts = {}
        
        for user_id in user_ids:
            result = odoo_search(
                model='res.partner',
                domain=[
                    ['user_id', '=', user_id],  # Un seul utilisateur à la fois
                    ['create_date', '>=', start_date],
                    ['create_date', '<=', end_date],
                    ['category_id', 'in', [CATEGORY_IDS["recommandation"]]]
                ],
                fields=['id']
            )
            
            response = json.loads(result)
            if response.get('status') == 'success':
                individual_counts[user_id] = response.get('returned_count', 0)
            else:
                individual_counts[user_id] = 0
        
        return individual_counts
        
    except Exception as e:
        raise Exception(f"Error getting individual recommendations count: {str(e)}")


def get_new_clients_count_individual(
    start_date: str, 
    end_date: str, 
    user_ids: List[int]
):
    """Get new clients count for each user individually"""
    try:
        individual_counts = {}

        for user_id in user_ids:
            result = odoo_search(
                model='sale.order',
                domain=[
                    ['create_date', '>=', start_date],
                    ['create_date', '<=', end_date],
                    ['user_id', '=', user_id]
                ],
                fields=['partner_id'],
                limit=10000  # Récupérer toutes les commandes pour ne rater aucun client
            )

            response = json.loads(result)
            if response.get('status') == 'success':
                partner_ids = list(set([
                    order['partner_id'][0]
                    for order in response.get('records', [])
                    if order.get('partner_id')
                ]))

                new_clients_count = 0
                for partner_id in partner_ids:
                    previous_orders = odoo_execute(
                        model='sale.order',
                        method='search_count',
                        args=[[
                            ['partner_id', '=', partner_id],
                            ['create_date', '<', start_date]
                        ]]
                    )

                    prev_response = json.loads(previous_orders)
                    if (prev_response.get('status') == 'success' and
                        prev_response.get('result', 0) == 0):
                        new_clients_count += 1

                individual_counts[user_id] = new_clients_count
            else:
                individual_counts[user_id] = 0

        return individual_counts

    except Exception as e:
        raise Exception(f"Error getting individual new clients count: {str(e)}")


def get_recommendations_details_individual(start_date: str, end_date: str, user_ids: List[int]):
    """Get detailed list of recommendations for each user individually"""
    try:
        individual_details = {}
        
        for user_id in user_ids:
            result = odoo_search(
                model='res.partner',
                domain=[
                    ['user_id', '=', user_id],
                    ['create_date', '>=', start_date],
                    ['create_date', '<=', end_date],
                    ['category_id', 'in', [CATEGORY_IDS["recommandation"]]]
                ],
                fields=['id', 'name'],
                limit=50
            )
            
            response = json.loads(result)
            if response.get('status') == 'success':
                contacts = []
                for contact in response.get('records', []):
                    contacts.append({
                        'id': contact['id'],
                        'name': contact.get('name', 'Contact sans nom')
                    })
                individual_details[user_id] = contacts
            else:
                individual_details[user_id] = []
        
        return individual_details
        
    except Exception as e:
        raise Exception(f"Error getting recommendations details: {str(e)}")

def get_new_clients_details_individual(start_date: str, end_date: str, user_ids: List[int]):
    """Get detailed list of new clients for each user individually"""
    try:
        individual_details = {}
        
        for user_id in user_ids:
            # Get orders in period for this specific user
            result = odoo_search(
                model='sale.order',
                domain=[
                    ['create_date', '>=', start_date],
                    ['create_date', '<=', end_date],
                    ['user_id', '=', user_id]
                ],
                fields=['partner_id'],
                limit=10000  # Récupérer toutes les commandes pour ne rater aucun client
            )
            
            response = json.loads(result)
            if response.get('status') == 'success':
                # Get unique partner IDs from orders for this user
                partner_ids = list(set([order['partner_id'][0] for order in response.get('records', []) if order.get('partner_id')]))
                
                new_clients = []
                for partner_id in partner_ids:
                    # Check if partner has any orders before start_date FROM THIS USER
                    previous_orders = odoo_search(
                        model='sale.order',
                        domain=[
                            ['partner_id', '=', partner_id],
                            ['create_date', '<', start_date],
                            ['user_id', '=', user_id]
                        ],
                        fields=['id'],
                        limit=1
                    )
                    
                    prev_response = json.loads(previous_orders)
                    if prev_response.get('status') == 'success' and prev_response.get('returned_count', 0) == 0:
                        # This is a new client, get their details
                        client_details = odoo_search(
                            model='res.partner',
                            domain=[['id', '=', partner_id]],
                            fields=['id', 'name'],
                            limit=1
                        )
                        
                        client_response = json.loads(client_details)
                        if client_response.get('status') == 'success' and client_response.get('records'):
                            client = client_response['records'][0]
                            new_clients.append({
                                'id': client['id'],
                                'name': client.get('name', 'Client sans nom')
                            })
                
                individual_details[user_id] = new_clients
            else:
                individual_details[user_id] = []
        
        return individual_details
        
    except Exception as e:
        raise Exception(f"Error getting new clients details: {str(e)}")

def get_recommendations_details_individual(start_date: str, end_date: str, user_ids: List[int]):
    """Get detailed list of recommendations for each user individually"""
    try:
        individual_details = {}
        
        for user_id in user_ids:
            result = odoo_search(
                model='res.partner',
                domain=[
                    ['user_id', '=', user_id],
                    ['create_date', '>=', start_date],
                    ['create_date', '<=', end_date],
                    ['category_id', 'in', [CATEGORY_IDS["recommandation"]]]
                ],
                fields=['id', 'name'],
                limit=50
            )
            
            response = json.loads(result)
            if response.get('status') == 'success':
                contacts = []
                for contact in response.get('records', []):
                    contacts.append({
                        'id': contact['id'],
                        'name': contact.get('name', 'Contact sans nom')
                    })
                individual_details[user_id] = contacts
            else:
                individual_details[user_id] = []
        
        return individual_details
        
    except Exception as e:
        raise Exception(f"Error getting recommendations details: {str(e)}")

def get_new_clients_details_individual(start_date: str, end_date: str, user_ids: List[int]):
    """Get detailed list of new clients for each user individually"""
    try:
        individual_details = {}
        
        for user_id in user_ids:
            # Get orders in period for this specific user
            result = odoo_search(
                model='sale.order',
                domain=[
                    ['create_date', '>=', start_date],
                    ['create_date', '<=', end_date],
                    ['user_id', '=', user_id]
                ],
                fields=['partner_id'],
                limit=10000  # Récupérer toutes les commandes pour ne rater aucun client
            )
            
            response = json.loads(result)
            if response.get('status') == 'success':
                # Get unique partner IDs from orders for this user
                partner_ids = list(set([order['partner_id'][0] for order in response.get('records', []) if order.get('partner_id')]))
                
                new_clients = []
                for partner_id in partner_ids:
                    # Check if partner has any orders before start_date FROM THIS USER
                    previous_orders = odoo_search(
                        model='sale.order',
                        domain=[
                            ['partner_id', '=', partner_id],
                            ['create_date', '<', start_date],
                            ['user_id', '=', user_id]
                        ],
                        fields=['id'],
                        limit=1
                    )
                    
                    prev_response = json.loads(previous_orders)
                    if prev_response.get('status') == 'success' and prev_response.get('returned_count', 0) == 0:
                        # This is a new client, get their details
                        client_details = odoo_search(
                            model='res.partner',
                            domain=[['id', '=', partner_id]],
                            fields=['id', 'name'],
                            limit=1
                        )
                        
                        client_response = json.loads(client_details)
                        if client_response.get('status') == 'success' and client_response.get('records'):
                            client = client_response['records'][0]
                            new_clients.append({
                                'id': client['id'],
                                'name': client.get('name', 'Client sans nom')
                            })
                
                individual_details[user_id] = new_clients
            else:
                individual_details[user_id] = []
        
        return individual_details
        
    except Exception as e:
        raise Exception(f"Error getting new clients details: {str(e)}")


def get_invoiced_clients_details_individual(start_date: str, end_date: str, user_ids: List[int], company_id: int = None):
    """
    Get detailed list of invoices with their clients for each user individually

    Args:
        start_date: Start date in ISO format
        end_date: End date in ISO format
        user_ids: List of user IDs
        company_id: Optional company ID to filter invoices by company

    Returns:
        Dict with user_id as key and list of invoices as value
        Each invoice contains: invoice_id, invoice_name, partner_id, partner_name
    """
    try:
        individual_details = {}

        for user_id in user_ids:
            # Get invoices in period for this specific user
            domain = [
                ['invoice_date', '>=', start_date],
                ['invoice_date', '<=', end_date],
                ['invoice_user_id', '=', user_id],
                ['move_type', '=', 'out_invoice'],
                ['state', '=', 'posted']
            ]

            # Add company filter if provided
            if company_id is not None:
                domain.append(['company_id', '=', company_id])

            result = odoo_search(
                model='account.move',
                domain=domain,
                fields=['id', 'name', 'partner_id'],
                limit=10000
            )

            response = json.loads(result)
            if response.get('status') == 'success':
                invoices = []
                for invoice in response.get('records', []):
                    if invoice.get('partner_id'):
                        invoices.append({
                            'invoice_id': invoice['id'],
                            'invoice_name': invoice.get('name', 'Facture sans nom'),
                            'partner_id': invoice['partner_id'][0],
                            'partner_name': invoice['partner_id'][1] if len(invoice['partner_id']) > 1 else 'Client sans nom'
                        })

                individual_details[user_id] = invoices
            else:
                individual_details[user_id] = []

        return individual_details

    except Exception as e:
        raise Exception(f"Error getting invoiced details: {str(e)}")


def get_ordering_clients_details_individual(start_date: str, end_date: str, user_ids: List[int]):
    """
    Get detailed list of orders with their clients for each user individually

    Args:
        start_date: Start date in ISO format
        end_date: End date in ISO format
        user_ids: List of user IDs

    Returns:
        Dict with user_id as key and list of orders as value
        Each order contains: order_id, order_name, partner_id, partner_name
    """
    try:
        individual_details = {}

        for user_id in user_ids:
            # Get orders in period for this specific user
            result = odoo_search(
                model='sale.order',
                domain=[
                    ['date_order', '>=', start_date],
                    ['date_order', '<=', end_date],
                    ['user_id', '=', user_id]
                ],
                fields=['id', 'name', 'partner_id'],
                limit=10000
            )

            response = json.loads(result)
            if response.get('status') == 'success':
                orders = []
                for order in response.get('records', []):
                    if order.get('partner_id'):
                        orders.append({
                            'order_id': order['id'],
                            'order_name': order.get('name', 'Commande sans nom'),
                            'partner_id': order['partner_id'][0],
                            'partner_name': order['partner_id'][1] if len(order['partner_id']) > 1 else 'Client sans nom'
                        })

                individual_details[user_id] = orders
            else:
                individual_details[user_id] = []

        return individual_details

    except Exception as e:
        raise Exception(f"Error getting ordering details: {str(e)}")


def get_delivered_clients_details_individual(start_date: str, end_date: str, user_ids: List[int]):
    """
    Get detailed list of deliveries with their clients for each user individually

    Args:
        start_date: Start date in ISO format
        end_date: End date in ISO format
        user_ids: List of user IDs

    Returns:
        Dict with user_id as key and list of deliveries as value
        Each delivery contains: picking_id, picking_name, partner_id, partner_name
    """
    try:
        individual_details = {}

        for user_id in user_ids:
            # Get deliveries in period for this specific user (outgoing only)
            result = odoo_search(
                model='stock.picking',
                domain=[
                    ['date_done', '>=', start_date],
                    ['date_done', '<=', end_date],
                    ['user_id', '=', user_id],
                    ['picking_type_code', '=', 'outgoing']  # Uniquement les livraisons clients
                ],
                fields=['id', 'name', 'partner_id'],
                limit=10000
            )

            response = json.loads(result)
            if response.get('status') == 'success':
                deliveries = []
                for picking in response.get('records', []):
                    if picking.get('partner_id'):
                        deliveries.append({
                            'picking_id': picking['id'],
                            'picking_name': picking.get('name', 'Livraison sans nom'),
                            'partner_id': picking['partner_id'][0],
                            'partner_name': picking['partner_id'][1] if len(picking['partner_id']) > 1 else 'Client sans nom'
                        })

                individual_details[user_id] = deliveries
            else:
                individual_details[user_id] = []

        return individual_details

    except Exception as e:
        raise Exception(f"Error getting delivery details: {str(e)}")


def collect_metrics_data(start_date: str, end_date: str, user_ids: List[int]):
    """
    Collect all business metrics for the report
    MODIFIÉ pour inclure les détails des clients/factures/commandes
    """
    try:
        # Get ALL company IDs for ALL users (needed for invoice details)
        all_company_ids = set()
        for user_id in user_ids:
            result = odoo_search(
                model='res.users',
                domain=[['id', '=', user_id]],
                fields=['company_ids'],
                limit=1
            )
            response = json.loads(result)
            if response.get('status') == 'success' and response.get('records'):
                company_ids = response['records'][0].get('company_ids', [])
                all_company_ids.update(company_ids)

        # Métriques AGRÉGÉES (comme avant)
        aggregated_metrics = {
            "rdv_places_total": get_appointments_placed(start_date, end_date, user_ids),
            "passer_voir": get_passer_voir_count(start_date, end_date, user_ids),  # Inclut maintenant CHR + GD
            "rdv_realises": get_appointments_realized(start_date, end_date, user_ids),  # Inclut maintenant CHR + GD
            "nombre_commandes_total": get_orders_count(start_date, end_date, user_ids),
            "recommandations_total": get_recommendations_count(start_date, end_date, user_ids),
            "livraisons": get_deliveries_count(start_date, end_date, user_ids),
            "relances_impayees_total": get_payment_reminders_count(start_date, end_date, user_ids)
        }

        # Métriques INDIVIDUELLES (compteurs)
        individual_metrics = {
            "rdv_places_individual": get_appointments_placed_individual(start_date, end_date, user_ids),
            "nombre_commandes_individual": get_orders_count_individual(start_date, end_date, user_ids),
            "recommandations_individual": get_recommendations_count_individual(start_date, end_date, user_ids),
            "nouveaux_clients_individual": get_new_clients_count_individual(start_date, end_date, user_ids),
            "relances_impayees_individual": get_payment_reminders_count_individual(start_date, end_date, user_ids)
        }

        # Détails INDIVIDUELS par société pour les factures
        # Structure: {company_id: {user_id: [invoices...]}}
        invoiced_details_by_company = {}
        for company_id in all_company_ids:
            invoiced_details_by_company[company_id] = get_invoiced_clients_details_individual(
                start_date, end_date, user_ids, company_id=company_id
            )

        # Détails INDIVIDUELS (listes de clients/commandes sans filtrage société)
        individual_details = {
            "recommandations_details_individual": get_recommendations_details_individual(start_date, end_date, user_ids),
            "nouveaux_clients_details_individual": get_new_clients_details_individual(start_date, end_date, user_ids),
            "invoiced_details_by_company": invoiced_details_by_company,  # NOUVEAU: factures par société
            "ordering_clients_details_individual": get_ordering_clients_details_individual(start_date, end_date, user_ids),
            "delivered_clients_details_individual": get_delivered_clients_details_individual(start_date, end_date, user_ids)
        }

        # Combiner tout
        return {
            **aggregated_metrics,
            **individual_metrics,
            **individual_details,
            "all_company_ids": list(all_company_ids)  # Retourner aussi les company_ids pour le HTML
        }

    except Exception as e:
        raise Exception(f"Error collecting metrics data: {str(e)}")


def strip_html_tags(html_text):
    """
    Remove HTML tags from text to get plain text.

    Args:
        html_text: HTML string to clean

    Returns:
        Plain text without HTML tags
    """
    if not html_text:
        return ""

    import re
    # Remove HTML tags
    clean = re.sub('<.*?>', '', html_text)
    # Remove extra whitespace
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()


def get_top_contact(user_ids: List[int], category_id: int):
    """
    MODIFIÉ pour supporter plusieurs utilisateurs et retourner ID + nom
    Retourne un dict avec 'id' et 'name' ou None si pas trouvé
    """
    try:
        result = odoo_search(
            model='res.partner',
            domain=[
                ['user_id', 'in', user_ids],
                ['category_id', 'in', [category_id]]
            ],
            fields=['id', 'name'],
            limit=1
        )

        response = json.loads(result)
        if response.get('status') == 'success' and response.get('records'):
            record = response['records'][0]
            return {
                'id': record['id'],
                'name': record['name']
            }
        return None

    except Exception as e:
        raise Exception(f"Error getting top contact: {str(e)}")


def get_tip_top_contacts(user_ids: List[int]):
    """MODIFIÉ pour supporter plusieurs utilisateurs"""
    try:
        result = odoo_search(
            model='res.partner',
            domain=[
                ['user_id', 'in', user_ids],  # CHANGÉ
                ['category_id', 'in', [CATEGORY_IDS["tip_top"]]]
            ],
            fields=['name'],
            limit=50
        )

        response = json.loads(result)
        if response.get('status') == 'success':
            return [contact['name'] for contact in response.get('records', [])]
        return []

    except Exception as e:
        raise Exception(f"Error getting tip top contacts: {str(e)}")


def collect_top5_client_activities(start_date: str, end_date: str, top_clients_data: Dict):
    """
    Collect chatter messages and activities for each Top 5 client.

    Args:
        start_date: Start date in ISO format
        end_date: End date in ISO format
        top_clients_data: Dict with top client data (from collect_top_clients_data)

    Returns:
        Dict with client activities data for each top client
    """
    try:
        top5_activities = {}

        for top_key in ['top_1', 'top_2', 'top_3', 'top_4', 'top_5']:
            client_data = top_clients_data.get(top_key)

            if client_data and client_data.get('id'):
                partner_id = client_data['id']
                partner_name = client_data['name']

                # Récupérer les messages du chatter (notes, comments, emails)
                messages_result = odoo_search(
                    model='mail.message',
                    domain=[
                        ['res_id', '=', partner_id],
                        ['model', '=', 'res.partner'],
                        ['date', '>=', start_date + ' 00:00:00'],
                        ['date', '<=', end_date + ' 23:59:59'],
                        ['message_type', 'in', ['comment', 'email']]  # Notes sont stockées comme comments
                    ],
                    fields=['date', 'body', 'author_id', 'message_type', 'subject'],
                    limit=100
                )

                messages = []
                messages_response = json.loads(messages_result)
                if messages_response.get('status') == 'success':
                    messages = messages_response.get('records', [])

                # Récupérer les activités terminées (avec protection contre les erreurs)
                activities = []
                try:
                    activities_result = odoo_search(
                        model='mail.activity',
                        domain=[
                            ['res_id', '=', partner_id],
                            ['res_model', '=', 'res.partner'],
                            ['date_done', '>=', start_date],
                            ['date_done', '<=', end_date],
                            ['state', '=', 'done']
                        ],
                        fields=['summary', 'date_done', 'note'],
                        limit=50
                    )

                    activities_response = json.loads(activities_result)
                    if activities_response.get('status') == 'success':
                        activities = activities_response.get('records', [])
                    else:
                        # Log l'erreur mais continue sans activités
                        print(f"[WARNING] Could not fetch activities for partner {partner_id}: {activities_response.get('error', 'Unknown error')}")
                except Exception as e:
                    # Ne pas faire planter tout le rapport si les activités échouent
                    print(f"[WARNING] Exception while fetching activities for partner {partner_id}: {str(e)}")
                    activities = []

                top5_activities[top_key] = {
                    'id': partner_id,
                    'name': partner_name,
                    'messages': messages,
                    'activities': activities
                }
            else:
                # Pas de client pour ce top
                top5_activities[top_key] = None

        return top5_activities

    except Exception as e:
        raise Exception(f"Error collecting top5 client activities: {str(e)}")


def collect_top_clients_data(user_ids: List[int]):
    """MODIFIÉ pour supporter plusieurs utilisateurs"""
    try:
        return {
            "top_1": get_top_contact(user_ids, CATEGORY_IDS["top_1"]),
            "top_2": get_top_contact(user_ids, CATEGORY_IDS["top_2"]),
            "top_3": get_top_contact(user_ids, CATEGORY_IDS["top_3"]),
            "top_4": get_top_contact(user_ids, CATEGORY_IDS["top_4"]),
            "top_5": get_top_contact(user_ids, CATEGORY_IDS["top_5"]),
            "tip_top": get_tip_top_contacts(user_ids)
        }

    except Exception as e:
        raise Exception(f"Error collecting top clients data: {str(e)}")


def generate_report_html_table(report_data):
    """
    Generate HTML table for business report in Odoo WYSIWYG format
    REFACTORISÉ pour la nouvelle structure CA individuel + totaux
    """
    try:
        user_info = report_data.get('user_info', {})
        revenue_data = report_data.get('revenue_data', {})
        metrics_data = report_data.get('metrics_data', {})
        top_clients_data = report_data.get('top_clients_data', {})

        # Récupérer les noms d'utilisateurs pour affichage
        user_ids = user_info.get('user_ids', [])
        user_names = user_info.get('user_names', [])
        user_name_map = dict(zip(user_ids, user_names))

        html = f"""
        <div class="container">
            <h2>Rapport Business - {
                user_info.get('combined_user_name', 'N/A')
                }</h2>
            <p><strong>Période:</strong> {
                user_info.get('start_date', 'N/A')
                } au {
                    user_info.get('end_date', 'N/A')
                    }</p>

            <table class="table table-bordered table-striped" style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                <thead style="background-color: #f8f9fa;">
                    <tr>
                        <th style="border: 1px solid #dee2e6; padding: 12px; text-align: left; font-weight: bold;">Métrique</th>
                        <th style="border: 1px solid #dee2e6; padding: 12px; text-align: right; font-weight: bold;">Valeur</th>
                    </tr>
                </thead>
                <tbody>
        """

        # Section CA - Format avec factures individuelles par société
        invoiced_details_by_company = metrics_data.get('invoiced_details_by_company', {})
        all_company_ids = metrics_data.get('all_company_ids', [])
        trademark_details = revenue_data.get('trademark_details', {})

        for key, value in revenue_data.items():
            if key.startswith('ca_facture_') and 'commercial_' in key and not key.endswith('_trademarks'):
                # Extraire société et user_id
                parts = key.split('_')
                company_name = parts[2].title()  # ca_facture_[company]_commercial_[id]
                user_id = int(parts[-1])
                user_name = user_name_map.get(user_id, f"User {user_id}")

                label = (f"Chiffre d'affaires facturé HT {company_name} "
                        f"- {user_name}")
                style = ""

                html += f"""
                    <tr style="{style}">
                        <td style="border: 1px solid #dee2e6; padding: 10px;">{label}</td>
                        <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{format_currency(value)}</td>
                    </tr>
                """

                # NOUVEAU: Ajouter les sous-lignes par marque commerciale
                company_key_lower = company_name.lower().replace('é', 'e').replace(' ', '_')
                trademark_key = f"ca_facture_{company_key_lower}_commercial_{user_id}_trademarks"

                if trademark_key in trademark_details:
                    trademarks = trademark_details[trademark_key]
                    if trademarks:
                        # Trier les marques par montant décroissant pour un meilleur affichage
                        sorted_trademarks = sorted(trademarks.items(), key=lambda x: x[1], reverse=True)

                        for trademark_name, trademark_amount in sorted_trademarks:
                            html += f"""
                                <tr style="background-color: #f8f9fa;">
                                    <td style="border: 1px solid #dee2e6; padding: 10px; padding-left: 30px; font-size: 0.95em; color: #6c757d;">
                                        └─ {trademark_name}
                                    </td>
                                    <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right; font-size: 0.95em; color: #6c757d;">
                                        {format_currency(trademark_amount)}
                                    </td>
                                </tr>
                            """

                # Trouver le company_id correspondant au company_name
                matching_company_id = None
                for company_id in all_company_ids:
                    if get_company_name(company_id) == company_name.lower().replace('é', 'e').replace(' ', '_'):
                        matching_company_id = company_id
                        break

                # Ajouter la ligne de détails des factures pour cette société et cet utilisateur
                if matching_company_id and matching_company_id in invoiced_details_by_company:
                    invoices = invoiced_details_by_company[matching_company_id].get(user_id, [])
                    if invoices:
                        detail_label = f"Factures émises - {user_name}"
                        invoices_list = "<br>".join([
                            f"• <a href='{ODOO_URL}/web#id={invoice['invoice_id']}&model=account.move&view_type=form'>{invoice['invoice_name']}</a> "
                            f"(<a href='{ODOO_URL}/web#id={invoice['partner_id']}&model=res.partner&view_type=form'>{invoice['partner_name']}</a>)"
                            for invoice in invoices
                        ])

                        html += f"""
                                <tr>
                                    <td style="border: 1px solid #dee2e6; padding: 10px;">{detail_label}</td>
                                    <td style="border: 1px solid #dee2e6; padding: 10px; text-align: left; font-size: 0.9em;">{invoices_list}</td>
                                </tr>
                        """

            elif key.startswith('ca_facture_') and key.endswith('_total'):
                # Total par société
                company_name = key.replace('ca_facture_', '').replace('_total', '').title()
                label = f"Chiffre d'affaires Total facturé HT {company_name}"
                style = "background-color: #e9ecef; font-weight: bold;"

                html += f"""
                    <tr style="{style}">
                        <td style="border: 1px solid #dee2e6; padding: 10px;">{label}</td>
                        <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{format_currency(value)}</td>
                    </tr>
                """

        # Section métriques AGRÉGÉES (celles qui restent combinées)
        aggregated_labels = {
            "passer_voir": "Passer Voir",
            "rdv_realises": "Rendez-vous réalisés",
            "livraisons": "Livraisons"
        }

        delivered_clients_details = metrics_data.get('delivered_clients_details_individual', {})

        for key, label in aggregated_labels.items():
            value = metrics_data.get(key, 0)
            html += f"""
                    <tr>
                        <td style="border: 1px solid #dee2e6; padding: 10px;">{label}</td>
                        <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{value}</td>
                    </tr>
            """

            # Ajouter les détails des livraisons effectuées après la ligne Livraisons
            if key == "livraisons" and delivered_clients_details:
                for user_id, deliveries in delivered_clients_details.items():
                    if deliveries:
                        user_name = user_name_map.get(user_id, f"User {user_id}")
                        detail_label = f"Livraisons effectuées - {user_name}"
                        deliveries_list = "<br>".join([
                            f"• <a href='{ODOO_URL}/web#id={delivery['picking_id']}&model=stock.picking&view_type=form'>{delivery['picking_name']}</a> "
                            f"(<a href='{ODOO_URL}/web#id={delivery['partner_id']}&model=res.partner&view_type=form'>{delivery['partner_name']}</a>)"
                            for delivery in deliveries
                        ])

                        html += f"""
                                <tr>
                                    <td style="border: 1px solid #dee2e6; padding: 10px;">{detail_label}</td>
                                    <td style="border: 1px solid #dee2e6; padding: 10px; text-align: left; font-size: 0.9em;">{deliveries_list}</td>
                                </tr>
                        """

        # Section métriques INDIVIDUELLES avec détails
        individual_metrics = {
            "rdv_places_individual": ("Nombre de rendez-vous placés", None),
            "nombre_commandes_individual": ("Nombre de commandes", "ordering_clients_details_individual"),
            "recommandations_individual": (
                "Nombre de recommandations",
                "recommandations_details_individual"
            ),
            "nouveaux_clients_individual": (
                "Nombre de nouveaux clients",
                "nouveaux_clients_details_individual"
            )
        }

        for metric_key, (base_label, details_key) in individual_metrics.items():
            individual_data = metrics_data.get(metric_key, {})
            details_data = metrics_data.get(details_key, {}) if details_key else {}

            if individual_data:
                for user_id, count in individual_data.items():
                    user_name = user_name_map.get(user_id, f"User {user_id}")
                    label = f"{base_label} - {user_name}"

                    # Ligne avec le nombre
                    html += f"""
                            <tr>
                                <td style="border: 1px solid #dee2e6; padding: 10px;">{label}</td>
                                <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{count}</td>
                            </tr>
                    """

                    # Ligne avec les détails (si applicable)
                    if details_key and user_id in details_data:
                        items = details_data[user_id]
                        if items:
                            # Déterminer le type de détails et formatter en conséquence
                            if details_key == "recommandations_details_individual":
                                detail_label = f"Contacts recommandés - {user_name}"
                                items_list = "<br>".join([
                                    f"• <a href='{ODOO_URL}/web#id={item['id']}&model=res.partner&view_type=form'>{item['name']}</a>"
                                    for item in items
                                ])
                            elif details_key == "nouveaux_clients_details_individual":
                                detail_label = f"Nouveaux clients - {user_name}"
                                items_list = "<br>".join([
                                    f"• <a href='{ODOO_URL}/web#id={item['id']}&model=res.partner&view_type=form'>{item['name']}</a>"
                                    for item in items
                                ])
                            elif details_key == "ordering_clients_details_individual":
                                detail_label = f"Commandes reçues - {user_name}"
                                items_list = "<br>".join([
                                    f"• <a href='{ODOO_URL}/web#id={item['order_id']}&model=sale.order&view_type=form'>{item['order_name']}</a> "
                                    f"(<a href='{ODOO_URL}/web#id={item['partner_id']}&model=res.partner&view_type=form'>{item['partner_name']}</a>)"
                                    for item in items
                                ])
                            else:
                                # Fallback pour d'autres types
                                detail_label = f"Détails - {user_name}"
                                items_list = "<br>".join([f"• {item}" for item in items])

                            html += f"""
                                    <tr>
                                        <td style="border: 1px solid #dee2e6; padding: 10px;">{detail_label}</td>
                                        <td style="border: 1px solid #dee2e6; padding: 10px; text-align: left; font-size: 0.9em;">{items_list}</td>
                                    </tr>
                            """

        # Section relances impayées - Afficher d'abord le total agrégé si plusieurs utilisateurs
        relances_impayees_total = metrics_data.get('relances_impayees_total', 0)
        relances_impayees_individual = metrics_data.get('relances_impayees_individual', {})

        # Si plusieurs utilisateurs, afficher d'abord le total
        if len(user_ids) > 1:
            html += f"""
                    <tr>
                        <td style="border: 1px solid #dee2e6; padding: 10px;">Nombre de relances impayés faites (Total)</td>
                        <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{relances_impayees_total}</td>
                    </tr>
            """

        # Afficher les détails par utilisateur
        for user_id, count in relances_impayees_individual.items():
            user_name = user_name_map.get(user_id, f"User {user_id}")
            label = f"Nombre de relances impayés faites - {user_name}"

            html += f"""
                    <tr>
                        <td style="border: 1px solid #dee2e6; padding: 10px;">{label}</td>
                        <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{count}</td>
                    </tr>
            """

        # Section ligne vide pour saisie manuelle (paiements récupérés)
        html += f"""
                <tr style="background-color: #fff3cd;">
                    <td style="border: 1px solid #dee2e6; padding: 10px;">Nombre de paiements récupérés</td>
                    <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right; font-style: italic; color: #6c757d;">À remplir</td>
                </tr>
        """

        # Section Top clients avec résumés AI
        top5_summaries = report_data.get('top5_summaries', {})

        top_labels = {
            "top_1": "Top 1",
            "top_2": "Top 2",
            "top_3": "Top 3",
            "top_4": "Top 4",
            "top_5": "Top 5",
            "tip_top": "Tip Top"
        }

        for key, label in top_labels.items():
            value = top_clients_data.get(key)

            # Affichage du nom du client avec lien hypertexte
            if key == "tip_top" and isinstance(value, list):
                display_value = ", ".join(value) if value else "Aucun"
            elif isinstance(value, dict):
                # Nouveau format: dict avec 'id' et 'name' - créer un lien
                if value and value.get('id'):
                    partner_id = value['id']
                    partner_name = value.get('name', 'Sans nom')
                    display_value = f"<a href='{ODOO_URL}/web#id={partner_id}&model=res.partner&view_type=form' style='color: #28a745; text-decoration: none;'>{partner_name}</a>"
                else:
                    display_value = "Aucun"
            else:
                # Ancien format (string) ou None
                display_value = value if value else "Aucun"

            html += f"""
                    <tr>
                        <td style="border: 1px solid #dee2e6; padding: 10px;">{label}</td>
                        <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{display_value}</td>
                    </tr>
            """

            # Afficher le résumé AI juste après pour les Top 1-5 (pas Tip Top)
            if key in ['top_1', 'top_2', 'top_3', 'top_4', 'top_5']:
                summary = top5_summaries.get(key, '')
                if summary:
                    html += f"""
                    <tr>
                        <td colspan="2" style="border: 1px solid #dee2e6; padding: 10px; background-color: #f8f9fa; font-style: italic;">
                            <strong>Actions menées:</strong><br>
                            {summary}
                        </td>
                    </tr>
                    """

        html += """
                </tbody>
            </table>
        </div>
        """

        return html

    except Exception as e:
        raise Exception(f"Error generating HTML table: {str(e)}")


def create_report_task(report_data, project_id, task_column_id):
    """
    Create an Odoo task with the business report
    CORRIGÉ pour gérer les valeurs None et la nouvelle structure user_info
    """
    try:
        user_info = report_data.get('user_info', {})
        # CORRIGÉ: utiliser combined_user_name au lieu de user_name
        combined_user_name = user_info.get('combined_user_name', 'N/A')
        start_date = user_info.get('start_date', 'N/A')
        end_date = user_info.get('end_date', 'N/A')
        user_ids = user_info.get('user_ids', [])

        # Generate task title
        task_name = f"Rapport Business - {combined_user_name} ({start_date} au {end_date})"

        # Generate HTML table
        html_description = generate_report_html_table(report_data)

        # CORRIGÉ: s'assurer qu'aucune valeur None n'est passée
        task_data = {
            'name': task_name,
            'project_id': project_id,
            'stage_id': task_column_id,
            'description': html_description,
        }

        # Ajouter les assignés seulement s'il y en a
        if user_ids:
            # Assigner à tous les utilisateurs du rapport
            task_data['user_ids'] = [(4, uid) for uid in user_ids if uid is not None]

        # Create task using odoo_execute
        result = odoo_execute(
            model='project.task',
            method='create',
            args=[task_data]
        )

        response = json.loads(result)
        if response.get('status') == 'success':
            task_id = response.get('result')
            return task_id
        else:
            raise Exception(f"Task creation failed: {response.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise Exception(f"Error creating report task: {str(e)}")


