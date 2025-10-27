"""
Activity report tool module.

Contains the activity_report MCP tool and all its helper functions.
"""

import json
import datetime
import pytz
import base64
from typing import List, Dict
from config import ODOO_DB, ODOO_PASSWORD, ODOO_URL, SUBTYPE_MAPPING
from services.odoo_client import get_odoo_connection
from services.formatters import strip_html_tags, extract_text_from_html
from services.ai import generate_claude_summary


# The mcp instance will be injected by the main module
mcp = None


def init_mcp(mcp_instance):
    """Initialize the mcp instance for this module"""
    global mcp
    mcp = mcp_instance
    
    # Register the tool
    mcp.tool()(odoo_activity_report)


# Import odoo_search and odoo_execute from data module
def odoo_search(*args, **kwargs):
    """Wrapper to call odoo_search from tools.data"""
    from tools.data import odoo_search as _odoo_search
    return _odoo_search(*args, **kwargs)


def odoo_execute(*args, **kwargs):
    """Wrapper to call odoo_execute from tools.data"""
    from tools.data import odoo_execute as _odoo_execute
    return _odoo_execute(*args, **kwargs)


def generate_pdf_from_html(html_content: str) -> bytes:
    """
    Convert HTML to PDF using WeasyPrint.

    Args:
        html_content: HTML string to convert

    Returns:
        bytes: PDF content as bytes
    """
    try:
        from weasyprint import HTML

        # Generate PDF in memory (no temporary file needed)
        pdf_bytes = HTML(string=html_content).write_pdf()

        return pdf_bytes

    except Exception as e:
        raise Exception(f"Error generating PDF from HTML: {str(e)}")


def attach_pdf_to_task_chatter(task_id: int, pdf_bytes: bytes, filename: str) -> int:
    """
    Attach a PDF file to an Odoo task and post it in the Chatter.

    Args:
        task_id: ID of the task to attach the PDF to
        pdf_bytes: PDF content as bytes
        filename: Name for the attachment file

    Returns:
        int: ID of the created attachment
    """
    try:
        # Encode PDF to base64
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

        # STEP 1: Create the attachment
        attachment_data = {
            'name': filename,
            'type': 'binary',
            'datas': pdf_base64,
            'res_model': 'project.task',
            'res_id': task_id,
            'mimetype': 'application/pdf'
        }

        result = odoo_execute(
            model='ir.attachment',
            method='create',
            args=[attachment_data]
        )

        response = json.loads(result)
        if response.get('status') != 'success':
            raise Exception(f"Attachment creation failed: {response.get('error', 'Unknown error')}")

        attachment_id = response.get('result')
        print(f"[SUCCESS] Created attachment #{attachment_id}: {filename}")

        # STEP 2: Post a message in the Chatter with the attachment
        message_data = {
            'body': '<p>📎 Timeline exhaustive jointe en PDF</p>',
            'model': 'project.task',
            'res_id': task_id,
            'message_type': 'comment',
            'attachment_ids': [(6, 0, [attachment_id])]  # Link the attachment to the message
        }

        message_result = odoo_execute(
            model='mail.message',
            method='create',
            args=[message_data]
        )

        message_response = json.loads(message_result)
        if message_response.get('status') == 'success':
            message_id = message_response.get('result')
            print(f"[SUCCESS] Posted message #{message_id} in Chatter with PDF attachment")
        else:
            print(f"[WARNING] Attachment created but failed to post in Chatter: {message_response.get('error')}")

        return attachment_id

    except Exception as e:
        raise Exception(f"Error attaching PDF to task: {str(e)}")


def odoo_activity_report(
    user_id: int,
    start_date: str,
    end_date: str,
    project_id: int,
    task_column_id: int
) -> str:
    """
    Generate a comprehensive daily timeline activity report for a user over a specified period.
    Uses the enriched timeline collection system to track all user activities day by day.

    Args:
        user_id: ID of the Odoo user to generate report for
        start_date: Start date in ISO format (YYYY-MM-DD)
        end_date: End date in ISO format (YYYY-MM-DD)
        project_id: ID of the project where the report task will be created
        task_column_id: ID of the task column/stage where the report will be placed

    Returns:
        JSON string with the complete activity report data
    """
    try:
        # Validate date format
        try:
            datetime.datetime.fromisoformat(start_date)
            datetime.datetime.fromisoformat(end_date)
        except ValueError:
            return json.dumps({
                "status": "error",
                "message": "Invalid date format. Use YYYY-MM-DD format."
            })

        # Validate that start_date is before or equal to end_date
        if start_date > end_date:
            return json.dumps({
                "status": "error",
                "message": "start_date must be before or equal to end_date"
            })

        # Test Odoo connection first
        models, uid = get_odoo_connection()

        # Verify user exists
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

        user_name = user_response['records'][0]['name']

        print(f"[INFO] Generating activity report for {user_name} (user_id={user_id}) from {start_date} to {end_date}")

        # PARTIE 1: Collecter les données pour le tableau récapitulatif
        print(f"[INFO] Collecting summary data (activities, tasks, projects)...")
        report_data = {
            "user_info": {
                "user_id": user_id,
                "user_name": user_name,
                "start_date": start_date,
                "end_date": end_date
            },
            "activities_data": collect_activities_data(start_date, end_date, user_id),
            "tasks_data": collect_tasks_data(start_date, end_date, user_id),
            "projects_data": collect_projects_data(start_date, end_date, user_id)
        }

        # PARTIE 2: Collecter la timeline enrichie pour la liste exhaustive
        print(f"[INFO] Collecting daily timeline data...")
        timeline_data = collect_daily_timeline_data(start_date, end_date, user_id)

        # PARTIE 3: Générer le tableau récapitulatif HTML (sans timeline)
        print(f"[INFO] Generating summary table HTML...")
        summary_table_html = generate_activity_report_html_table(report_data)

        # PARTIE 4: Créer la tâche avec uniquement le tableau récapitulatif
        task_name = f"Rapport d'activité - {user_name} ({start_date} au {end_date})"
        print(f"[INFO] Creating report task with summary table...")
        task_id = create_activity_report_task(
            task_name=task_name,
            html_content=summary_table_html,
            project_id=project_id,
            task_column_id=task_column_id,
            user_id=user_id
        )

        # PARTIE 5: Générer la timeline exhaustive HTML pour PDF
        print(f"[INFO] Generating detailed timeline HTML for PDF...")
        timeline_html = generate_daily_timeline_html(timeline_data)

        # PARTIE 6: Générer le PDF de la timeline
        print(f"[INFO] Converting timeline HTML to PDF...")
        pdf_bytes = generate_pdf_from_html(timeline_html)
        pdf_size = len(pdf_bytes)
        print(f"[SUCCESS] PDF generated successfully ({pdf_size} bytes)")

        # PARTIE 7: Attacher le PDF à la tâche dans le Chatter
        print(f"[INFO] Attaching PDF to task Chatter...")
        pdf_filename = f"timeline_{user_name.replace(' ', '_')}_{start_date}_{end_date}.pdf"
        attachment_id = attach_pdf_to_task_chatter(task_id, pdf_bytes, pdf_filename)

        # Count total events for summary
        total_events = sum(len(events) for events in timeline_data.values())

        task_url = f"{ODOO_URL}/web#id={task_id}&model=project.task&view_type=form"

        return json.dumps({
            "status": "success",
            "message": f"Activity report generated successfully for {user_name}",
            "period": f"{start_date} to {end_date}",
            "task_id": task_id,
            "task_name": task_name,
            "task_url": task_url,
            "total_days": len(timeline_data),
            "total_events": total_events,
            "pdf_attachment": {
                "attachment_id": attachment_id,
                "filename": pdf_filename,
                "size_bytes": pdf_size
            },
            "timestamp": datetime.datetime.now().isoformat()
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Error generating activity report: {str(e)}"
        })


def enrich_messages_with_display_names(messages: list) -> dict:
    """
    Récupère les display_name réels des records en batch pour optimiser les performances.
    Grouper par modèle permet de faire une seule requête par modèle au lieu d'une par message.

    Args:
        messages: Liste des messages mail.message

    Returns:
        Dict {(model, res_id): display_name} pour lookup rapide
    """
    display_names = {}

    # Grouper les IDs par modèle
    records_by_model = {}
    for msg in messages:
        model = msg.get('model')
        res_id = msg.get('res_id')

        if model and res_id:
            if model not in records_by_model:
                records_by_model[model] = set()
            records_by_model[model].add(res_id)

    # Récupérer les display_name en batch par modèle
    for model, ids in records_by_model.items():
        try:
            ids_list = list(ids)
            result = odoo_search(
                model=model,
                domain=[['id', 'in', ids_list]],
                fields=['id', 'display_name'],
                limit=len(ids_list)
            )

            result_data = json.loads(result)
            if result_data.get('status') == 'success':
                for record in result_data.get('records', []):
                    key = (model, record['id'])
                    display_names[key] = record.get('display_name', f"{model}#{record['id']}")
        except Exception as e:
            # En cas d'erreur sur un modèle, on continue avec les autres
            print(f"Warning: Could not fetch display_names for model {model}: {str(e)}")
            continue

    return display_names


def determine_action_type(msg: dict) -> str:
    """
    Determine the action type based on mail.message attributes using SUBTYPE_MAPPING.

    Args:
        msg: mail.message record with message_type, subtype_id fields

    Returns:
        Human-readable action type (e.g., 'Création', 'Email', 'Note', 'Tâche créée')
    """
    message_type = msg.get('message_type', 'notification')
    subtype_id = msg.get('subtype_id')

    # Email envoyé/reçu
    if message_type == 'email':
        return 'Email'

    # Note interne / commentaire
    if message_type == 'comment':
        return 'Commentaire'

    # Notification système (création, modification, etc.)
    if message_type == 'notification':
        # Vérifier le contenu du body pour détecter des cas spécifiques
        # IMPORTANT : Nettoyer le HTML AVANT de chercher le texte
        body_html = msg.get('body', '') or msg.get('preview', '')
        body_text = extract_text_from_html(body_html, max_length=None)
        body_lower = body_text.lower()

        # Détecter "To-Do terminée" ou activité terminée
        if 'to-do terminée' in body_lower or 'todo terminée' in body_lower:
            return 'To-Do terminée'

        # Utiliser le mapping des subtypes pour identifier l'action précise
        if subtype_id:
            # subtype_id est un tuple [id, "nom"] ou juste un int
            subtype_numeric_id = subtype_id[0] if isinstance(subtype_id, list) else subtype_id
            subtype_name = subtype_id[1] if isinstance(subtype_id, list) else str(subtype_id)

            # Chercher dans le mapping
            if subtype_numeric_id in SUBTYPE_MAPPING:
                return SUBTYPE_MAPPING[subtype_numeric_id]

            # Fallback sur l'analyse du nom si pas dans le mapping
            subtype_lower = subtype_name.lower()
            if 'created' in subtype_lower or 'création' in subtype_lower or 'créé' in subtype_lower:
                return 'Création'
            elif 'stage' in subtype_lower or 'étape' in subtype_lower:
                return 'Changement d\'étape'
            elif 'update' in subtype_lower or 'modif' in subtype_lower:
                return 'Modification'
            elif 'won' in subtype_lower or 'gagné' in subtype_lower:
                return 'Opportunité gagnée'
            elif 'lost' in subtype_lower or 'perdu' in subtype_lower:
                return 'Opportunité perdue'
            elif 'done' in subtype_lower or 'terminé' in subtype_lower:
                return 'Terminé'

        return 'Notification'

    return 'Action'


def build_action_name(msg: dict, action_type: str, enriched_display_name: str = None) -> str:
    """
    Build an ultra-explicit descriptive name for the action.
    Format: {Action} sur {Type d'objet} "{Nom de l'objet}" : {Complément}

    Args:
        msg: mail.message record
        action_type: Action type from determine_action_type()
        enriched_display_name: Real display_name retrieved from batch enrichment (optional)

    Returns:
        Ultra-explicit action description
    """
    # Utiliser le display_name enrichi en priorité, sinon fallback sur record_name
    record_name = enriched_display_name or msg.get('record_name', '') or f"#{msg.get('res_id', '?')}"

    # Récupérer le type d'objet en français
    model = msg.get('model', '')
    model_type = get_model_display_name(model)

    # EMAIL
    if action_type == 'Email':
        subject = msg.get('subject', 'Sans objet')
        return f'Email "{subject}" concernant {model_type} "{record_name}"'

    # COMMENTAIRE / NOTE INTERNE
    elif action_type == 'Commentaire':
        # Extraire un aperçu du contenu
        preview = msg.get('preview', '')
        if not preview:
            body = msg.get('body', '')
            preview = extract_text_from_html(body, max_length=100)

        if preview:
            return f'Note interne sur {model_type} "{record_name}" : {preview}'
        else:
            return f'Note interne sur {model_type} "{record_name}"'

    # TÂCHE CRÉÉE
    elif action_type == 'Tâche créée':
        return f'{model_type} créée : "{record_name}"'

    # TÂCHE TERMINÉE
    elif action_type == 'Tâche terminée':
        return f'{model_type} terminée : "{record_name}"'

    # CHANGEMENT D'ÉTAPE
    elif action_type == 'Changement d\'étape':
        return f'Changement d\'étape de {model_type} "{record_name}"'

    # TO-DO TERMINÉE
    elif action_type == 'To-Do terminée':
        # Essayer d'extraire le résumé de l'activité depuis le body (sans limite)
        body = msg.get('body', '')
        activity_summary = extract_text_from_html(body, max_length=None)
        if activity_summary:
            # Formater sur plusieurs lignes pour plus de lisibilité
            return (f'To-Do terminée\n'
                   f'   • Résumé : {activity_summary}\n'
                   f'   • Sur : {model_type} "{record_name}"')
        return f'To-Do terminée sur {model_type} "{record_name}"'

    # ACTIVITÉ PLANIFIÉE
    elif action_type == 'Activité planifiée':
        # Essayer d'extraire le résumé de l'activité depuis le body (sans limite)
        body = msg.get('body', '')
        activity_summary = extract_text_from_html(body, max_length=None)
        if activity_summary:
            # Formater sur plusieurs lignes pour plus de lisibilité
            return (f'Activité planifiée\n'
                   f'   • Résumé : {activity_summary}\n'
                   f'   • Sur : {model_type} "{record_name}"')
        return f'Activité planifiée sur {model_type} "{record_name}"'

    # OPPORTUNITÉ GAGNÉE/PERDUE
    elif action_type in ['Opportunité gagnée', 'Opportunité perdue']:
        return f'{action_type} : "{record_name}"'

    # FACTURE VALIDÉE/PAYÉE/CRÉÉE
    elif action_type in ['Facture validée', 'Facture payée', 'Facture créée']:
        return f'{action_type} : "{record_name}"'

    # NOTE INTERNE (autre cas)
    elif action_type == 'Note interne':
        preview = msg.get('preview', '') or extract_text_from_html(msg.get('body', ''), max_length=100)
        if preview:
            return f'Note interne sur {model_type} "{record_name}" : {preview}'
        return f'Note interne sur {model_type} "{record_name}"'

    # DISCUSSION
    elif action_type == 'Discussion':
        return f'Discussion sur {model_type} "{record_name}"'

    # NOTIFICATION ou autre type générique
    else:
        # Pour toutes les autres actions, format explicite avec le type d'objet
        return f'{action_type} sur {model_type} "{record_name}"'


def extract_text_from_html(html_content: str, max_length: int = None) -> str:
    """
    Extrait le texte propre depuis du HTML en retirant toutes les balises.

    Args:
        html_content: Contenu HTML à nettoyer
        max_length: Longueur maximale du texte extrait (None = pas de limite)

    Returns:
        Texte propre sans HTML, tronqué si nécessaire
    """
    if not html_content:
        return ""

    import re

    # ÉTAPE 1 : Convertir les balises HTML de saut de ligne en \n AVANT de supprimer les balises
    html_with_newlines = html_content
    # Remplacer les balises de bloc par des sauts de ligne
    html_with_newlines = re.sub(r'</p>', '\n', html_with_newlines, flags=re.IGNORECASE)
    html_with_newlines = re.sub(r'</div>', '\n', html_with_newlines, flags=re.IGNORECASE)
    html_with_newlines = re.sub(r'</li>', '\n', html_with_newlines, flags=re.IGNORECASE)
    html_with_newlines = re.sub(r'</h[1-6]>', '\n', html_with_newlines, flags=re.IGNORECASE)
    html_with_newlines = re.sub(r'<br\s*/?>', '\n', html_with_newlines, flags=re.IGNORECASE)
    html_with_newlines = re.sub(r'</tr>', '\n', html_with_newlines, flags=re.IGNORECASE)

    # ÉTAPE 2 : Supprimer toutes les balises HTML restantes
    text = strip_html_tags(html_with_newlines).strip()

    # ÉTAPE 3 : Nettoyer les espaces multiples LIGNE PAR LIGNE (préserver les newlines)
    lines = text.split('\n')
    cleaned_lines = [' '.join(line.split()) for line in lines]
    text = '\n'.join(line for line in cleaned_lines if line.strip())

    # ÉTAPE 4 : Tronquer si trop long (seulement si max_length est spécifié)
    if max_length and len(text) > max_length:
        text = text[:max_length] + "..."

    return text


def get_model_display_name(model: str) -> str:
    """
    Get a human-readable display name for Odoo model.

    Args:
        model: Technical model name (e.g., 'res.partner')

    Returns:
        Display name in French (e.g., 'Contact')
    """
    model_map = {
        'res.partner': 'Contact',
        'crm.lead': 'Opportunité',
        'sale.order': 'Commande',
        'account.move': 'Facture',
        'project.task': 'Tâche',
        'project.project': 'Projet',
        'product.product': 'Produit',
        'product.template': 'Produit',
        'purchase.order': 'Bon de commande',
        'stock.picking': 'Livraison',
        'mail.activity': 'Activité',
        'calendar.event': 'Événement',
        'maintenance.equipment': 'Équipement',
        'maintenance.request': 'Maintenance',
        'hr.employee': 'Employé',
        'hr.applicant': 'Candidat',
        'project.update': 'Mise à jour projet',
    }

    # Fallback: prendre le dernier mot après le point et le capitaliser
    return model_map.get(model, model.split('.')[-1].title())


def convert_utc_to_paris(utc_datetime_str: str) -> str:
    """
    Convert UTC datetime string to Europe/Paris timezone.

    Args:
        utc_datetime_str: DateTime string in ISO format (may include 'Z' or '+00:00')

    Returns:
        ISO format datetime string in Europe/Paris timezone
    """
    try:
        # Normaliser le format UTC (remplacer Z par +00:00)
        if utc_datetime_str.endswith('Z'):
            utc_datetime_str = utc_datetime_str.replace('Z', '+00:00')

        # Parser le datetime UTC
        event_datetime_utc = datetime.datetime.fromisoformat(utc_datetime_str)

        # Définir la timezone Paris
        paris_tz = pytz.timezone('Europe/Paris')

        # Convertir en heure locale
        if event_datetime_utc.tzinfo is None:
            # Si pas de timezone, assumer UTC
            utc_tz = pytz.UTC
            event_datetime_utc = utc_tz.localize(event_datetime_utc)

        event_datetime_paris = event_datetime_utc.astimezone(paris_tz)

        return event_datetime_paris.isoformat()

    except Exception as e:
        # En cas d'erreur, retourner la valeur originale
        print(f"[WARNING] Erreur conversion timezone pour {utc_datetime_str}: {str(e)}")
        return utc_datetime_str


def collect_daily_timeline_data(start_date: str, end_date: str, user_id: int):
    """
    Collect ALL user actions via mail.message (comprehensive tracking) + mail.activity (completed activities).
    Organizes events chronologically day by day with timestamps.

    This captures:
    - All tracked actions on records (creation, status changes, field updates)
    - Emails sent/received
    - Internal notes and comments
    - Completed activities (from mail.activity)

    Returns:
        Dict with dates as keys and list of events sorted by time
    """
    try:
        all_events = []

        # 1. Récupérer le partner_id associé au user_id
        # Nécessaire car mail.message utilise author_id (res.partner) ET create_uid (res.users)
        # Quand un user crée une notification système, le message a create_uid = user_id mais author_id = partner_id
        user_result = odoo_search(
            model='res.users',
            domain=[['id', '=', user_id]],
            fields=['partner_id'],
            limit=1
        )
        user_data = json.loads(user_result)
        if user_data.get('status') != 'success' or not user_data.get('records'):
            raise Exception(f"Cannot find user {user_id}")

        partner_id = user_data['records'][0]['partner_id'][0]

        # 2. MAIL.MESSAGE - Capture TOUT ce qui est tracké dans Odoo
        # Utilise un filtre OR pour capturer:
        # - create_uid: notifications système créées par le user
        # - author_id: notes/emails écrits par le partner
        messages_result = odoo_search(
            model='mail.message',
            domain=[
                '|',
                ['create_uid', '=', user_id],      # Notifs système créées par le user
                ['author_id', '=', partner_id],    # Notes/emails écrits par le partner
                ['date', '>=', start_date],
                ['date', '<=', end_date]
            ],
            fields=[
                'id', 'subject', 'body', 'preview', 'date', 'model', 'res_id',
                'message_type', 'subtype_id', 'record_name',
                # Champs enrichis accessibles sans droits admin
                'attachment_ids',      # Pièces jointes
                'partner_ids',         # Utilisateurs tagués
                'email_from',          # Expéditeur email
                # Champs nécessitant droits admin (désactivés)
                # 'tracking_value_ids',  # Nécessite groupe Administration/Settings
                # Champs secondaires (non nécessaires pour l'instant)
                # 'is_internal', 'record_company_id', 'parent_id', 'mail_activity_type_id',
                # 'rating_value', 'starred', 'pinned_at'
            ],
            limit=100000  # Limite très élevée pour historique complet (inatteignable en pratique)
        )
        messages_response = json.loads(messages_result)

        # DEBUG: Log de la réponse brute
        print(f"[DEBUG] Statut de la requête mail.message : {messages_response.get('status')}")
        if messages_response.get('status') != 'success':
            print(f"[DEBUG] ERREUR dans la requête mail.message: {messages_response.get('error', 'Erreur inconnue')}")

        # Enrichir les messages avec les vrais display_name en batch
        messages_list = messages_response.get('records', []) if messages_response.get('status') == 'success' else []
        display_names_map = enrich_messages_with_display_names(messages_list)

        # DEBUG: Log du nombre de messages récupérés
        print(f"[DEBUG] Messages récupérés de mail.message : {len(messages_list)}")

        if messages_response.get('status') == 'success':
            filtered_count = 0
            for msg in messages_list:
                if msg.get('date') and msg.get('model') and msg.get('res_id'):
                    filtered_count += 1
                    # Récupérer le vrai display_name depuis le map
                    enriched_name = display_names_map.get((msg['model'], msg['res_id']), None)

                    # Déterminer le type d'action basé sur message_type et subtype
                    action_type = determine_action_type(msg)

                    # Construire un nom descriptif pour l'action avec le vrai nom
                    action_name = build_action_name(msg, action_type, enriched_name)

                    # Convertir le timestamp UTC en heure locale Paris
                    datetime_paris = convert_utc_to_paris(msg['date'])

                    all_events.append({
                        'datetime': datetime_paris,  # Timestamp converti en heure locale
                        'type': action_type,
                        'name': action_name,
                        'id': msg['res_id'],  # ID du record concerné (pas du message)
                        'model': msg['model'],
                        'url': f"{ODOO_URL}/web#id={msg['res_id']}&model={msg['model']}&view_type=form",
                        'message_id': msg['id'],  # Gardé pour référence
                        # Champs enrichis accessibles
                        'subject': msg.get('subject'),
                        'body': msg.get('body'),
                        'preview': msg.get('preview'),
                        'record_name': enriched_name or msg.get('record_name'),
                        'message_type': msg.get('message_type'),
                        'subtype_id': msg.get('subtype_id'),
                        'attachment_ids': msg.get('attachment_ids', []),
                        'partner_ids': msg.get('partner_ids', []),
                        'email_from': msg.get('email_from'),
                        # Champs non récupérés (nécessitent droits admin ou non nécessaires)
                        # 'tracking_value_ids', 'is_internal', 'record_company_id', 'parent_id',
                        # 'mail_activity_type_id', 'rating_value', 'starred', 'pinned_at'
                    })
                else:
                    # DEBUG: Log des messages filtrés
                    print(f"[DEBUG] Message filtré (id={msg.get('id')}): date={msg.get('date')}, model={msg.get('model')}, res_id={msg.get('res_id')}")

            # DEBUG: Log du nombre de messages après filtrage
            print(f"[DEBUG] Messages après filtrage (date/model/res_id présents) : {filtered_count}")

        # 2. MAIL.ACTIVITY - Activités terminées (complément pour ce qui n'est pas dans mail.message)
        activities_result = odoo_search(
            model='mail.activity',
            domain=[
                ['active', '=', False],
                ['state', '=', 'done'],
                ['date_done', '>=', start_date],
                ['date_done', '<=', end_date],
                ['user_id', '=', user_id]
            ],
            fields=['id', 'summary', 'date_done', 'res_model', 'res_id', 'res_name'],
            limit=100000  # Limite très élevée pour historique complet (inatteignable en pratique)
        )
        activities_response = json.loads(activities_result)
        if activities_response.get('status') == 'success':
            for activity in activities_response.get('records', []):
                if activity.get('date_done'):
                    # Format ultra-explicite : Activité "{Résumé}" sur {Type} : {Nom objet}
                    summary = activity.get('summary', 'Activité sans nom')
                    res_model = activity.get('res_model', '')
                    res_name = activity.get('res_name', f"#{activity.get('res_id', '?')}")
                    model_type = get_model_display_name(res_model)

                    # Format final explicite
                    activity_name = f'Activité "{summary}" sur {model_type} : {res_name}'

                    # Convertir le timestamp UTC en heure locale Paris
                    # Note: date_done est de type date (pas datetime), mais on le convertit quand même
                    datetime_paris = convert_utc_to_paris(activity['date_done'])

                    all_events.append({
                        'datetime': datetime_paris,  # Timestamp converti en heure locale
                        'type': 'Activité',
                        'name': activity_name,
                        'id': activity.get('res_id', activity['id']),
                        'model': activity.get('res_model', 'mail.activity'),
                        'url': f"{ODOO_URL}/web#id={activity.get('res_id', activity['id'])}&model={activity.get('res_model', 'mail.activity')}&view_type=form"
                    })

        # DEBUG: Log du nombre total d'événements avant tri
        print(f"[DEBUG] Total événements ajoutés à all_events (messages + activités) : {len(all_events)}")

        # DEBUG: Log d'un échantillon de timestamps convertis
        if all_events:
            sample_event = all_events[0]
            print(f"[DEBUG] Exemple de timestamp converti: {sample_event.get('datetime')} pour événement '{sample_event.get('name', 'N/A')[:50]}'")

        # Trier tous les événements par datetime
        all_events.sort(key=lambda x: x['datetime'])

        # Grouper par jour avec DEUX listes séparées
        # Raison: Les activités n'ont pas d'heure (champ date_done est de type date, pas datetime)
        # donc on les sépare visuellement des autres événements qui ont des timestamps précis
        daily_timeline = {}
        current_date = datetime.datetime.fromisoformat(start_date)
        end_date_obj = datetime.datetime.fromisoformat(end_date)

        # Générer tous les jours de la période avec structure à deux listes
        while current_date <= end_date_obj:
            date_str = current_date.strftime('%Y-%m-%d')
            daily_timeline[date_str] = {
                'activites': [],  # Activités sans timestamp (date_done = date only)
                'autres_evenements': []  # Autres événements avec timestamp précis
            }
            current_date += datetime.timedelta(days=1)

        # DEBUG: Log des jours générés dans daily_timeline
        print(f"[DEBUG] Jours générés dans daily_timeline : {list(daily_timeline.keys())}")

        # Répartir les événements dans les bonnes listes
        events_distributed = 0
        events_outside_range = 0
        for event in all_events:
            event_date = event['datetime'][:10]  # Extract YYYY-MM-DD
            if event_date in daily_timeline:
                events_distributed += 1
                if event['type'] == 'Activité':
                    # Les activités vont dans leur propre section (pas d'heure affichée)
                    daily_timeline[event_date]['activites'].append(event)
                else:
                    # Tout le reste a un timestamp précis
                    daily_timeline[event_date]['autres_evenements'].append(event)
            else:
                events_outside_range += 1
                # DEBUG: Log des événements hors plage
                print(f"[DEBUG] Événement hors plage ({event_date} not in timeline): {event.get('name', 'N/A')}")

        # DEBUG: Log du nombre d'événements distribués
        print(f"[DEBUG] Événements distribués dans daily_timeline : {events_distributed}")
        print(f"[DEBUG] Événements hors plage de dates : {events_outside_range}")

        # DEBUG: Log du contenu de chaque jour
        for date_key, date_events in daily_timeline.items():
            total_day_events = len(date_events['activites']) + len(date_events['autres_evenements'])
            if total_day_events > 0:
                print(f"[DEBUG] {date_key}: {len(date_events['activites'])} activités + {len(date_events['autres_evenements'])} autres événements = {total_day_events} total")

        return daily_timeline

    except Exception as e:
        raise Exception(f"Error collecting daily timeline data: {str(e)}")


def collect_activities_data(
        start_date: str,
        end_date: str,
        user_id: int
        ):
    """Collect all activities data for the report"""
    try:
        today = datetime.datetime.now().strftime('%Y-%m-%d')

        # Nombres (comme avant)
        activites_realisees_count = get_activity_count([
            ['active', '=', False],
            ['state', '=', 'done'],
            ['date_done', '>=', start_date],
            ['date_done', '<=', end_date],
            ['user_id', '=', user_id]
        ])

        activites_retard = get_activity_count([
            ['active', '=', True],
            ['state', '!=', 'done'],
            ['date_deadline', '<', today],
            ['user_id', '=', user_id]
        ])

        activites_delais = get_activity_count([
            ['active', '=', True],
            ['state', '!=', 'done'],
            ['date_deadline', '>=', today],
            ['user_id', '=', user_id]
        ])

        activites_cours_total = get_activity_count([
            ['active', '=', True],
            ['state', '!=', 'done'],
            ['user_id', '=', user_id]
        ])

        # Listes détaillées (nouveau)
        activites_realisees_details = get_completed_activities_details(
            start_date,
            end_date,
            user_id
            )

        # Timeline chronologique jour par jour (nouveau)
        daily_timeline = collect_daily_timeline_data(start_date, end_date, user_id)

        return {
            "activites_realisees": activites_realisees_count,
            "activites_retard": activites_retard,
            "activites_delais": activites_delais,
            "activites_cours_total": activites_cours_total,
            "activites_realisees_details": activites_realisees_details,
            "daily_timeline": daily_timeline
        }

    except Exception as e:
        raise Exception(f"Error collecting activities data: {str(e)}")


def collect_tasks_data(
        start_date: str,
        end_date: str,
        user_id: int
        ):
    """Collect all tasks data for the report"""
    try:
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # Nombres (comme avant)
        taches_realisees_count = get_task_count([
            ['user_ids', 'in', [user_id]],
            ['state', '=', '1_done'],
            ['date_last_stage_update', '>=', start_date],
            ['date_last_stage_update', '<=', end_date]
        ])
        
        taches_retard = get_task_count([
            ['user_ids', 'in', [user_id]],
            ['state', '=', '01_in_progress'],
            ['date_deadline', '!=', False],
            ['date_deadline', '<', today]
        ])
        
        taches_delais = get_task_count([
            ['user_ids', 'in', [user_id]],
            ['state', '=', '01_in_progress'],
            ['date_deadline', '!=', False],
            ['date_deadline', '>=', today]
        ])
        
        taches_sans_delais = get_task_count([
            ['user_ids', 'in', [user_id]],
            ['state', '=', '01_in_progress'],
            ['date_deadline', '=', False]
        ])
        
        taches_cours_total = get_task_count([
            ['user_ids', 'in', [user_id]],
            ['state', '=', '01_in_progress']
        ])
        
        # Listes détaillées (nouveau)
        taches_realisees_details = get_completed_tasks_details(start_date, end_date, user_id)
        
        return {
            "taches_realisees": taches_realisees_count,
            "taches_retard": taches_retard,
            "taches_delais": taches_delais,
            "taches_sans_delais": taches_sans_delais,
            "taches_cours_total": taches_cours_total,
            "taches_realisees_details": taches_realisees_details
        }
        
    except Exception as e:
        raise Exception(f"Error collecting tasks data: {str(e)}")

def collect_projects_data(start_date: str, end_date: str, user_id: int):
    """Collect all projects data for the report"""
    try:
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # Nombres (comme avant)
        projets_realises_count = get_completed_projects_count(start_date, end_date, user_id)
        
        projets_retard = get_project_count([
            '|',
            ['user_id', '=', user_id],
            ['favorite_user_ids', 'in', [user_id]],
            ['last_update_status', '!=', 'done'],
            ['date', '!=', False],
            ['date', '<', today]
        ])
        
        projets_delais = get_project_count([
            '|',
            ['user_id', '=', user_id],
            ['favorite_user_ids', 'in', [user_id]],
            ['last_update_status', '!=', 'done'],
            ['date', '!=', False],
            ['date', '>=', today]
        ])
        
        projets_sans_dates = get_project_count([
            '|',
            ['user_id', '=', user_id],
            ['favorite_user_ids', 'in', [user_id]],
            ['last_update_status', '!=', 'done'],
            ['date', '=', False]
        ])
        
        projets_cours_total = get_project_count([
            '|',
            ['user_id', '=', user_id],
            ['favorite_user_ids', 'in', [user_id]],
            ['last_update_status', '!=', 'done']
        ])
        
        # Listes détaillées (nouveau)
        projets_realises_details = get_completed_projects_details(start_date, end_date, user_id)
        
        return {
            "projets_realises": projets_realises_count,
            "projets_retard": projets_retard,
            "projets_delais": projets_delais,
            "projets_sans_dates": projets_sans_dates,
            "projets_cours_total": projets_cours_total,
            "projets_realises_details": projets_realises_details
        }
        
    except Exception as e:
        raise Exception(f"Error collecting projects data: {str(e)}")

def get_completed_activities_details(start_date: str, end_date: str, user_id: int):
    """Get detailed list of completed activities with links"""
    try:
        result = odoo_search(
            model='mail.activity',
            domain=[
                ['active', '=', False],
                ['state', '=', 'done'],
                ['date_done', '>=', start_date],
                ['date_done', '<=', end_date], 
                ['user_id', '=', user_id]
            ],
            fields=['id', 'summary', 'date_done', 'res_model', 'res_id', 'note', 'activity_type_id'],
            limit=50
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            activities = []
            for activity in response.get('records', []):
                activity_url = f"{ODOO_URL}/web#id={activity['id']}&model=mail.activity&view_type=form"
                # Extract additional fields
                note = activity.get('note', '') or ''
                # Clean HTML from note
                import re
                note_clean = re.sub(r'<[^>]*>', '', note).strip() if note else ''
                activity_type = activity.get('activity_type_id', [False, 'N/A'])[1] if activity.get('activity_type_id') else 'N/A'
                related_model = activity.get('res_model', 'N/A')

                activities.append({
                    'name': activity.get('summary', 'Activité sans nom'),
                    'url': activity_url,
                    'date': activity.get('date_done', ''),
                    'note': note_clean[:200] + '...' if len(note_clean) > 200 else note_clean,
                    'type': activity_type,
                    'related_model': related_model
                })
            return activities
        return []
        
    except Exception as e:
        raise Exception(f"Error getting completed activities details: {str(e)}")

def get_completed_tasks_details(start_date: str, end_date: str, user_id: int):
    """Get detailed list of completed tasks with links"""
    try:
        result = odoo_search(
            model='project.task',
            domain=[
                ['user_ids', 'in', [user_id]],
                ['state', '=', '1_done'],
                ['date_last_stage_update', '>=', start_date],
                ['date_last_stage_update', '<=', end_date]
            ],
            fields=['id', 'name', 'date_last_stage_update', 'project_id', 'description', 'tag_ids', 'partner_id'],
            limit=50
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            tasks = []
            for task in response.get('records', []):
                task_url = f"{ODOO_URL}/web#id={task['id']}&model=project.task&view_type=form"
                # Extract additional fields
                project_name = task.get('project_id', [False, 'N/A'])[1] if task.get('project_id') else 'N/A'
                client_name = task.get('partner_id', [False, 'N/A'])[1] if task.get('partner_id') else 'N/A'
                description = task.get('description', '') or ''
                # Clean HTML from description
                import re
                description_clean = re.sub(r'<[^>]*>', '', description).strip() if description else ''

                tasks.append({
                    'name': task.get('name', 'Tâche sans nom'),
                    'url': task_url,
                    'date': task.get('date_last_stage_update', ''),
                    'project': project_name,
                    'client': client_name,
                    'description': description_clean[:200] + '...' if len(description_clean) > 200 else description_clean,
                    'tag_ids': task.get('tag_ids', [])
                })
            return tasks
        return []
        
    except Exception as e:
        raise Exception(f"Error getting completed tasks details: {str(e)}")

def get_completed_projects_details(start_date: str, end_date: str, user_id: int):
    """Get detailed list of completed projects with links"""
    try:
        # Étape 1: Chercher les project.update avec status="done" dans la période
        updates_result = odoo_search(
            model='project.update',
            domain=[
                ['status', '=', 'done'],
                ['date', '>=', start_date], 
                ['date', '<=', end_date]
            ],
            fields=['project_id', 'date'],
            limit=50
        )
        
        updates_response = json.loads(updates_result)
        if updates_response.get('status') != 'success':
            return []
        
        # Récupérer les IDs des projets avec leur date de completion
        project_updates = {}
        for update in updates_response.get('records', []):
            if update.get('project_id'):
                project_id = update['project_id'][0]
                project_updates[project_id] = update.get('date', '')
        
        if not project_updates:
            return []
        
        # Étape 2: Récupérer les détails des projets où l'utilisateur participe
        projects_result = odoo_search(
            model='project.project',
            domain=[
                ['id', 'in', list(project_updates.keys())],
                '|',
                ['user_id', '=', user_id],
                ['favorite_user_ids', 'in', [user_id]]
            ],
            fields=['id', 'name', 'description', 'partner_id', 'tag_ids'],
            limit=50
        )
        
        projects_response = json.loads(projects_result)
        if projects_response.get('status') == 'success':
            projects = []
            for project in projects_response.get('records', []):
                project_url = f"{ODOO_URL}/web#id={project['id']}&model=project.project&view_type=kanban"
                # Extract additional fields
                description = project.get('description', '') or ''
                # Clean HTML from description
                import re
                description_clean = re.sub(r'<[^>]*>', '', description).strip() if description else ''
                client_name = project.get('partner_id', [False, 'N/A'])[1] if project.get('partner_id') else 'N/A'

                projects.append({
                    'name': project.get('name', 'Projet sans nom'),
                    'url': project_url,
                    'date': project_updates.get(project['id'], ''),
                    'description': description_clean[:200] + '...' if len(description_clean) > 200 else description_clean,
                    'client': client_name,
                    'tag_ids': project.get('tag_ids', [])
                })
            return projects
        return []
        
    except Exception as e:
        raise Exception(f"Error getting completed projects details: {str(e)}")


def get_activity_count(domain):
    """Get count of mail.activity with given domain"""
    try:
        result = odoo_execute(
            model='mail.activity',
            method='search_count',
            args=[domain]
        )

        response = json.loads(result)
        if response.get('status') == 'success':
            return response.get('result', 0)
        else:
            raise Exception(
                f"Search failed: {
                    response.get(
                        'error', 'Unknown error'
                        )
                        }"
                        )

    except Exception as e:
        raise Exception(f"Error getting activity count: {str(e)}")


def get_task_count(domain):
    """Get count of project.task with given domain"""
    try:
        result = odoo_execute(
            model='project.task',
            method='search_count',
            args=[domain]
        )

        response = json.loads(result)
        if response.get('status') == 'success':
            return response.get('result', 0)
        else:
            raise Exception(
                f"Search failed: {
                    response.get(
                        'error', 'Unknown error'
                        )
                        }"
                        )

    except Exception as e:
        raise Exception(f"Error getting task count: {str(e)}")


def get_project_count(domain):
    """Get count of project.project with given domain"""
    try:
        result = odoo_search(
            model='project.project',
            domain=domain,
            fields=['id']
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            return response.get('returned_count', 0)
        else:
            raise Exception(f"Search failed: {response.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise Exception(f"Error getting project count: {str(e)}")

def get_completed_projects_count(start_date: str, end_date: str, user_id: int):
    """Get count of projects completed in period (complex logic with project.update)"""
    try:
        # Étape 1: Chercher les project.update avec status="done" dans la période
        updates_result = odoo_search(
            model='project.update',
            domain=[
                ['status', '=', 'done'],
                ['date', '>=', start_date],
                ['date', '<=', end_date]
            ],
            fields=['project_id']
        )

        updates_response = json.loads(updates_result)
        if updates_response.get('status') != 'success':
            raise Exception(f"Updates search failed: {updates_response.get('error', 'Unknown error')}")

        # Récupérer les IDs des projets
        project_ids = []
        for update in updates_response.get('records', []):
            if update.get('project_id'):
                project_ids.append(update['project_id'][0])

        if not project_ids:
            return 0

        # Étape 2: Compter les projets où l'utilisateur participe
        completed_projects_result = odoo_execute(
            model='project.project',
            method='search_count',
            args=[[
                ['id', 'in', project_ids],
                '|',
                ['user_id', '=', user_id],
                ['favorite_user_ids', 'in', [user_id]]
            ]]
        )

        completed_response = json.loads(completed_projects_result)
        if completed_response.get('status') == 'success':
            return completed_response.get('result', 0)
        else:
            raise Exception(f"Projects search failed: {completed_response.get('error', 'Unknown error')}")

    except Exception as e:
        raise Exception(f"Error getting completed projects count: {str(e)}")


def collect_activities_data(
        start_date: str,
        end_date: str,
        user_id: int
        ):
    """Collect all activities data for the report"""
    try:
        today = datetime.datetime.now().strftime('%Y-%m-%d')

        # Nombres (comme avant)
        activites_realisees_count = get_activity_count([
            ['active', '=', False],
            ['state', '=', 'done'],
            ['date_done', '>=', start_date],
            ['date_done', '<=', end_date],
            ['user_id', '=', user_id]
        ])

        activites_retard = get_activity_count([
            ['active', '=', True],
            ['state', '!=', 'done'],
            ['date_deadline', '<', today],
            ['user_id', '=', user_id]
        ])

        activites_delais = get_activity_count([
            ['active', '=', True],
            ['state', '!=', 'done'],
            ['date_deadline', '>=', today],
            ['user_id', '=', user_id]
        ])

        activites_cours_total = get_activity_count([
            ['active', '=', True],
            ['state', '!=', 'done'],
            ['user_id', '=', user_id]
        ])

        # Listes détaillées (nouveau)
        activites_realisees_details = get_completed_activities_details(
            start_date,
            end_date,
            user_id
            )

        return {
            "activites_realisees": activites_realisees_count,
            "activites_retard": activites_retard,
            "activites_delais": activites_delais,
            "activites_cours_total": activites_cours_total,
            "activites_realisees_details": activites_realisees_details
        }

    except Exception as e:
        raise Exception(f"Error collecting activities data: {str(e)}")


def collect_tasks_data(
        start_date: str,
        end_date: str,
        user_id: int
        ):
    """Collect all tasks data for the report"""
    try:
        today = datetime.datetime.now().strftime('%Y-%m-%d')

        # Nombres (comme avant)
        taches_realisees_count = get_task_count([
            ['user_ids', 'in', [user_id]],
            ['state', '=', '1_done'],
            ['date_last_stage_update', '>=', start_date],
            ['date_last_stage_update', '<=', end_date]
        ])

        taches_retard = get_task_count([
            ['user_ids', 'in', [user_id]],
            ['state', '=', '01_in_progress'],
            ['date_deadline', '!=', False],
            ['date_deadline', '<', today]
        ])

        taches_delais = get_task_count([
            ['user_ids', 'in', [user_id]],
            ['state', '=', '01_in_progress'],
            ['date_deadline', '!=', False],
            ['date_deadline', '>=', today]
        ])

        taches_sans_delais = get_task_count([
            ['user_ids', 'in', [user_id]],
            ['state', '=', '01_in_progress'],
            ['date_deadline', '=', False]
        ])

        taches_cours_total = get_task_count([
            ['user_ids', 'in', [user_id]],
            ['state', '=', '01_in_progress']
        ])

        # Listes détaillées (nouveau)
        taches_realisees_details = get_completed_tasks_details(start_date, end_date, user_id)

        return {
            "taches_realisees": taches_realisees_count,
            "taches_retard": taches_retard,
            "taches_delais": taches_delais,
            "taches_sans_delais": taches_sans_delais,
            "taches_cours_total": taches_cours_total,
            "taches_realisees_details": taches_realisees_details
        }

    except Exception as e:
        raise Exception(f"Error collecting tasks data: {str(e)}")


def collect_projects_data(start_date: str, end_date: str, user_id: int):
    """Collect all projects data for the report"""
    try:
        today = datetime.datetime.now().strftime('%Y-%m-%d')

        # Nombres (comme avant)
        projets_realises_count = get_completed_projects_count(start_date, end_date, user_id)

        projets_retard = get_project_count([
            '|',
            ['user_id', '=', user_id],
            ['favorite_user_ids', 'in', [user_id]],
            ['last_update_status', '!=', 'done'],
            ['date', '!=', False],
            ['date', '<', today]
        ])

        projets_delais = get_project_count([
            '|',
            ['user_id', '=', user_id],
            ['favorite_user_ids', 'in', [user_id]],
            ['last_update_status', '!=', 'done'],
            ['date', '!=', False],
            ['date', '>=', today]
        ])

        projets_sans_dates = get_project_count([
            '|',
            ['user_id', '=', user_id],
            ['favorite_user_ids', 'in', [user_id]],
            ['last_update_status', '!=', 'done'],
            ['date', '=', False]
        ])

        projets_cours_total = get_project_count([
            '|',
            ['user_id', '=', user_id],
            ['favorite_user_ids', 'in', [user_id]],
            ['last_update_status', '!=', 'done']
        ])

        # Listes détaillées (nouveau)
        projets_realises_details = get_completed_projects_details(start_date, end_date, user_id)

        return {
            "projets_realises": projets_realises_count,
            "projets_retard": projets_retard,
            "projets_delais": projets_delais,
            "projets_sans_dates": projets_sans_dates,
            "projets_cours_total": projets_cours_total,
            "projets_realises_details": projets_realises_details
        }

    except Exception as e:
        raise Exception(f"Error collecting projects data: {str(e)}")


def format_activity_html(activity):
    """Format a single activity in the new style"""
    name = activity.get('name', 'Activité sans nom')
    url = activity.get('url', '#')

    html = f"""
    <div style="margin-left: 20px; margin-bottom: 15px;">
        ✓ {name}
        <div style="margin-left: 20px; color: #6c757d; font-size: 0.9em;">
            └─ Lien : <a href="{url}" style="color: #007bff;">{url}</a>
        </div>
    </div>
    """
    return html


def format_message_html(event):
    """Format a single message event in the new detailed style"""
    try:
        # Extraire l'heure
        try:
            event_datetime = datetime.datetime.fromisoformat(event['datetime'].replace('Z', '+00:00'))
            time_str = event_datetime.strftime('%H:%M')
        except:
            time_str = '00:00'

        # Titre en majuscules basé sur le type
        title = event.get('type', 'ACTION').upper()

        # Section "Ce qui s'est passé"
        what_happened = event.get('name', 'Action non spécifiée')

        # Section "Où ça se passe"
        model_display = get_model_display_name(event.get('model', ''))
        record_name = event.get('record_name', 'N/A')
        doc_url = event.get('url', '#')

        html = f"""
        <div style="margin: 20px 0; padding: 15px; border: 1px solid #dee2e6; border-radius: 5px; background-color: #f8f9fa;">
            <div style="border-bottom: 2px solid #495057; padding-bottom: 5px; margin-bottom: 10px;">
                <strong>{time_str} | {title}</strong>
            </div>

            <p style="margin: 10px 0;"><strong>Ce qui s'est passé</strong></p>
            <div style="margin-left: 20px; white-space: pre-wrap;">{what_happened}</div>

            <p style="margin: 10px 0;"><strong>Où ça se passe</strong></p>
            <div style="margin-left: 20px;">
                • Type : {model_display}<br/>
                • Nom : {record_name}<br/>
                • Voir le document : <a href="{doc_url}" style="color: #007bff;">{doc_url}</a>
            </div>
        """

        # Section conditionnelle : Corps du message
        # Utiliser le body complet plutôt que le preview qui est pré-tronqué par Odoo
        body = event.get('body')
        if body and body.strip():
            # Extraire le texte complet du body HTML
            body_text = extract_text_from_html(body, max_length=None)
            if body_text:
                html += f"""
            <p style="margin: 10px 0;"><strong>Contenu du message</strong></p>
            <div style="margin-left: 20px; font-style: italic; color: #6c757d; white-space: pre-wrap;">{body_text}</div>
            """

        # Section conditionnelle : Email
        if event.get('message_type') == 'email':
            subject = event.get('subject', 'Sans sujet')
            email_from = event.get('email_from', 'N/A')
            html += f"""
            <p style="margin: 10px 0;"><strong>Email envoyé</strong></p>
            <div style="margin-left: 20px;">
                • Sujet : {subject}<br/>
                • De : {email_from}
            </div>
            """

        # Section conditionnelle : Pièces jointes
        attachment_ids = event.get('attachment_ids', [])
        if attachment_ids and len(attachment_ids) > 0:
            count = len(attachment_ids)
            html += f"""
            <p style="margin: 10px 0;"><strong>Fichiers joints</strong></p>
            <div style="margin-left: 20px;">📎 {count} fichier(s) joint(s)</div>
            """

        # Section conditionnelle : Utilisateurs tagués
        partner_ids = event.get('partner_ids', [])
        if partner_ids and len(partner_ids) > 0:
            html += f"""
            <p style="margin: 10px 0;"><strong>Utilisateurs concernés</strong></p>
            <div style="margin-left: 20px;">🏷️ {len(partner_ids)} utilisateur(s) tagué(s)</div>
            """

        # Détails du message
        msg_url = f"{ODOO_URL}/web#id={event.get('message_id')}&model=mail.message&view_type=form"

        html += f"""
            <p style="margin: 10px 0;"><strong>Détails du message</strong></p>
            <div style="margin-left: 20px; font-size: 0.85em; color: #6c757d;">
                • Voir le message : <a href="{msg_url}" style="color: #007bff;">{msg_url}</a><br/>
                • Type : {event.get('message_type', 'N/A')}
            </div>
        </div>
        """

        return html

    except Exception as e:
        return f"<div style='color: red;'>Erreur formatage événement: {str(e)}</div>"


def generate_daily_timeline_html(daily_timeline):
    """
    Generate HTML for day-by-day chronological timeline of all activities.
    NEW VERSION with enriched format and detailed sections.

    Args:
        daily_timeline: Dict with dates as keys and list of events as values

    Returns:
        HTML string with chronological timeline
    """
    try:
        # Convertir les jours français
        french_days = {
            0: 'Lundi',
            1: 'Mardi',
            2: 'Mercredi',
            3: 'Jeudi',
            4: 'Vendredi',
            5: 'Samedi',
            6: 'Dimanche'
        }

        html = """
        <div style="margin-top: 40px;">
            <h2 style="border-bottom: 2px solid #dee2e6; padding-bottom: 10px;">📋 Historique exhaustif de toutes les actions</h2>
            <p style="font-style: italic; color: #6c757d; margin-top: 10px;">
                Format enrichi avec détails complets pour chaque action :
                créations, modifications, emails, notes, changements, activités terminées, etc.
            </p>
        """

        # Trier les dates (du plus ancien au plus récent)
        sorted_dates = sorted(daily_timeline.keys())

        for date_str in sorted_dates:
            day_data = daily_timeline[date_str]
            activites = day_data['activites']
            autres_evenements = day_data['autres_evenements']

            # Parser la date pour affichage
            date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
            day_name = french_days[date_obj.weekday()]
            formatted_date = f"{day_name} {date_obj.strftime('%d/%m/%Y')}"

            html += f"""
            <div style="margin-top: 30px; margin-bottom: 30px; padding: 20px; border: 2px solid #007bff; border-radius: 8px; background-color: #ffffff;">
                <h3 style="background: linear-gradient(to right, #007bff, #0056b3); color: white; padding: 12px; border-radius: 5px; margin-bottom: 20px;">
                    📅 {formatted_date}
                </h3>
            """

            # Vérifier si le jour est complètement vide
            if not activites and not autres_evenements:
                html += """
                <p style="margin-left: 20px; font-style: italic; color: #6c757d;">Aucune activité</p>
                """
            else:
                # Section 1: Activités terminées
                if activites:
                    html += f"""
                    <h3 style="margin-left: 10px; margin-top: 20px; color: #28a745; border-bottom: 2px solid #28a745; padding-bottom: 5px;">
                        📋 ACTIVITÉS TERMINÉES ({len(activites)})
                    </h3>
                    """

                    for activity in activites:
                        html += format_activity_html(activity)

                # Section 2: Autres événements (messages)
                if autres_evenements:
                    html += f"""
                    <h3 style="margin-left: 10px; margin-top: 30px; color: #17a2b8; border-bottom: 2px solid #17a2b8; padding-bottom: 5px;">
                        ⏱️ AUTRES ÉVÉNEMENTS ({len(autres_evenements)})
                    </h3>
                    """

                    for event in autres_evenements:
                        html += format_message_html(event)

            html += '</div>'

        html += '</div>'

        return html

    except Exception as e:
        raise Exception(f"Error generating daily timeline HTML: {str(e)}")


def generate_activity_report_html_table(report_data):
    """Generate HTML table for activity report with detailed lists"""
    try:
        user_info = report_data.get('user_info', {})
        activities_data = report_data.get('activities_data', {})
        tasks_data = report_data.get('tasks_data', {})
        projects_data = report_data.get('projects_data', {})
        
        html = f"""
        <div class="container">
            <h2>Rapport d'activité - {user_info.get('user_name', 'N/A')}</h2>
            <p><strong>Période:</strong> {user_info.get('start_date', 'N/A')} au {user_info.get('end_date', 'N/A')}</p>
            
            <table class="table table-bordered table-striped" style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                <thead style="background-color: #f8f9fa;">
                    <tr>
                        <th style="border: 1px solid #dee2e6; padding: 12px; text-align: left; font-weight: bold;">Métrique</th>
                        <th style="border: 1px solid #dee2e6; padding: 12px; text-align: right; font-weight: bold;">Valeur</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        # Section Activités
        html += '<tr style="background-color: #e9ecef; font-weight: bold;"><td colspan="2" style="border: 1px solid #dee2e6; padding: 10px;">ACTIVITÉS</td></tr>'
        
        # Nombre d'activités réalisées
        html += f"""
                <tr>
                    <td style="border: 1px solid #dee2e6; padding: 10px;">Nombre d'activités réalisées dans la période donnée</td>
                    <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{activities_data.get('activites_realisees', 0)}</td>
                </tr>
        """
        
        # Liste des activités réalisées
        activites_details = activities_data.get('activites_realisees_details', [])
        activites_list = ""
        if activites_details:
            activites_list = "<br>".join([f"• <a href='{act['url']}'>{act['name']}</a> ({act['date']})" for act in activites_details])
        else:
            activites_list = "Aucune activité réalisée"
            
        html += f"""
                <tr>
                    <td style="border: 1px solid #dee2e6; padding: 10px;">Activités réalisées dans la période donnée</td>
                    <td style="border: 1px solid #dee2e6; padding: 10px; text-align: left; font-size: 0.9em;">{activites_list}</td>
                </tr>
        """
        
        # Autres métriques d'activités
        activities_labels = {
            "activites_retard": "Nombre d'activités en retard",
            "activites_delais": "Nombre d'activités dans les délais", 
            "activites_cours_total": "Nombre total d'activités en cours"
        }
        
        for key, label in activities_labels.items():
            value = activities_data.get(key, 0)
            html += f"""
                    <tr>
                        <td style="border: 1px solid #dee2e6; padding: 10px;">{label}</td>
                        <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{value}</td>
                    </tr>
            """
        
        # Section Tâches
        html += '<tr style="background-color: #e9ecef; font-weight: bold;"><td colspan="2" style="border: 1px solid #dee2e6; padding: 10px;">TÂCHES</td></tr>'
        
        # Nombre de tâches réalisées
        html += f"""
                <tr>
                    <td style="border: 1px solid #dee2e6; padding: 10px;">Nombre de tâches réalisées dans la période donnée</td>
                    <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{tasks_data.get('taches_realisees', 0)}</td>
                </tr>
        """
        
        # Liste des tâches réalisées
        taches_details = tasks_data.get('taches_realisees_details', [])
        taches_list = ""
        if taches_details:
            taches_list = "<br>".join([f"• <a href='{task['url']}'>{task['name']}</a> - {task['project']} ({task['date']})" for task in taches_details])
        else:
            taches_list = "Aucune tâche réalisée"
            
        html += f"""
                <tr>
                    <td style="border: 1px solid #dee2e6; padding: 10px;">Tâches réalisées dans la période donnée</td>
                    <td style="border: 1px solid #dee2e6; padding: 10px; text-align: left; font-size: 0.9em;">{taches_list}</td>
                </tr>
        """
        
        # Autres métriques de tâches
        tasks_labels = {
            "taches_retard": "Nombre de tâches en retard",
            "taches_delais": "Nombre de tâches dans les délais",
            "taches_sans_delais": "Nombre de tâches sans délais",
            "taches_cours_total": "Nombre total de tâches en cours"
        }
        
        for key, label in tasks_labels.items():
            value = tasks_data.get(key, 0)
            html += f"""
                    <tr>
                        <td style="border: 1px solid #dee2e6; padding: 10px;">{label}</td>
                        <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{value}</td>
                    </tr>
            """
        
        # Section Projets
        html += '<tr style="background-color: #e9ecef; font-weight: bold;"><td colspan="2" style="border: 1px solid #dee2e6; padding: 10px;">PROJETS</td></tr>'
        
        # Nombre de projets réalisés
        html += f"""
                <tr>
                    <td style="border: 1px solid #dee2e6; padding: 10px;">Nombre de projets réalisés dans la période donnée</td>
                    <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{projects_data.get('projets_realises', 0)}</td>
                </tr>
        """
        
        # Liste des projets réalisés
        projets_details = projects_data.get('projets_realises_details', [])
        projets_list = ""
        if projets_details:
            projets_list = "<br>".join([f"• <a href='{proj['url']}'>{proj['name']}</a> ({proj['date']})" for proj in projets_details])
        else:
            projets_list = "Aucun projet réalisé"
            
        html += f"""
                <tr>
                    <td style="border: 1px solid #dee2e6; padding: 10px;">Projets réalisés dans la période donnée</td>
                    <td style="border: 1px solid #dee2e6; padding: 10px; text-align: left; font-size: 0.9em;">{projets_list}</td>
                </tr>
        """
        
        # Autres métriques de projets
        projects_labels = {
            "projets_retard": "Nombre de projets en retard",
            "projets_delais": "Nombre de projets dans les délais",
            "projets_sans_dates": "Nombre de projets sans dates",
            "projets_cours_total": "Nombre total de projets en cours"
        }
        
        for key, label in projects_labels.items():
            value = projects_data.get(key, 0)
            html += f"""
                    <tr>
                        <td style="border: 1px solid #dee2e6; padding: 10px;">{label}</td>
                        <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{value}</td>
                    </tr>
            """
        
        # Add Claude AI summary row
        html += '<tr style="background-color: #e9ecef; font-weight: bold;"><td colspan="2" style="border: 1px solid #dee2e6; padding: 10px;">RÉSUMÉ IA</td></tr>'

        # Generate Claude summary
        user_name = user_info.get('user_name', 'cet utilisateur')
        start_date = user_info.get('start_date', '')
        end_date = user_info.get('end_date', '')

        claude_summary = generate_claude_summary(
            activities_data, tasks_data, projects_data,
            user_name, start_date, end_date
        )

        html += f"""
                <tr>
                    <td style="border: 1px solid #dee2e6; padding: 10px;"><strong>Résumé des activités</strong></td>
                    <td style="border: 1px solid #dee2e6; padding: 10px; text-align: left;">{claude_summary}</td>
                </tr>
        """

        html += """
                </tbody>
            </table>
        </div>
        """

        # NOTE: La timeline exhaustive n'est plus incluse ici
        # Elle sera générée en PDF séparé et attachée à la tâche

        return html

    except Exception as e:
        raise Exception(f"Error generating HTML table: {str(e)}")

def create_activity_report_task(task_name, html_content, project_id, task_column_id, user_id):
    """
    Create an Odoo task with the activity report.

    Args:
        task_name: Name of the task to create
        html_content: HTML content for the task description
        project_id: ID of the project where the task will be created
        task_column_id: ID of the stage/column where the task will be placed
        user_id: ID of the user to assign the task to

    Returns:
        Task ID of the created task
    """
    try:
        # Create task using odoo_execute
        result = odoo_execute(
            model='project.task',
            method='create',
            args=[{
                'name': task_name,
                'project_id': project_id,
                'stage_id': task_column_id,
                'description': html_content,
                'user_ids': [(4, user_id)]  # Assign to the user
            }]
        )

        response = json.loads(result)
        if response.get('status') == 'success':
            task_id = response.get('result')
            print(f"[SUCCESS] Created task #{task_id}: {task_name}")
            return task_id
        else:
            raise Exception(f"Task creation failed: {response.get('error', 'Unknown error')}")

    except Exception as e:
        raise Exception(f"Error creating activity report task: {str(e)}")




if __name__ == "__main__":
    # Run the server with SSE transport
    mcp.run(transport="sse")
