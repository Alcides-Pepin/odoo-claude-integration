"""
Configuration pour les rapports automatiques hebdomadaires.
Modifie ce fichier pour ajouter/retirer des utilisateurs ou changer les destinations.
"""

# Rapports d'activité - un rapport par utilisateur
ACTIVITY_REPORTS = [
    {"user_id": 747, "project_id": 211, "task_column_id": 942},  # Adrien Massart-Lambert
    {"user_id": 21, "project_id": 83, "task_column_id": 477},   # Agathe Férat
    {"user_id": 7, "project_id": 158, "task_column_id": 726},    # Alcides De Oliveira Guerra
    {"user_id": 863, "project_id": 189, "task_column_id": 844},  # Alexandre Schmitt
    {"user_id": 16, "project_id": 79, "task_column_id": 116},   # Amandine Aubry
    {"user_id": 208, "project_id": 42, "task_column_id": 219},  # Antoine Hemmerlé
    {"user_id": 701, "project_id": 181, "task_column_id": 789},  # Antonina Onishchenko
    {"user_id": 17, "project_id": 45, "task_column_id": 138},   # Axel Aragoncillo
    {"user_id": 13, "project_id": 20, "task_column_id": 112},   # Axel Lemarinier
    # {"user_id": 784, "project_id": 151, "task_column_id": 726},  # Budoc Doan
    {"user_id": 9, "project_id": 25, "task_column_id": 126},    # Cameron Price
    {"user_id": 537, "project_id": 139, "task_column_id": 725},  # Carla Rodriguez
    {"user_id": 862, "project_id": 190, "task_column_id": 848},  # Corentin Dumont
    {"user_id": 212, "project_id": 163, "task_column_id": 961},  # Daniel Bonifassi
    {"user_id": 909, "project_id": 211, "task_column_id": 942},  # Darius Pautrat
    {"user_id": 211, "project_id": 126, "task_column_id": 315},  # Emeric Acker
    # {"user_id": 770, "project_id": 151, "task_column_id": 726},  # Erika Runser
    # {"user_id": 464, "project_id": 151, "task_column_id": 726},  # Fleur Kornmann
    {"user_id": 215, "project_id": 59, "task_column_id": 315},  # Hubert Herphelin
    {"user_id": 302, "project_id": 135, "task_column_id": 653},  # Hugo Wahl
    {"user_id": 703, "project_id": 181, "task_column_id": 789},  # Inès Vedrenne
    {"user_id": 218, "project_id": 79, "task_column_id": 116},  # Justine Clément
    {"user_id": 695, "project_id": 25, "task_column_id": 126},  # Khalil Eddine Djerbi
    # {"user_id": 709, "project_id": 40, "task_column_id": 203},  # Lancelot Minoggio
    {"user_id": 22, "project_id": 35, "task_column_id": 240},   # Louise Quintrand
    {"user_id": 843, "project_id": 95, "task_column_id": 502},  # Marie Bedin
    {"user_id": 786, "project_id": 158, "task_column_id": 726},  # Mattis Almeida Lima
    {"user_id": 207, "project_id": 40, "task_column_id": 203},  # Maxime Guedou
    {"user_id": 6, "project_id": 31, "task_column_id": 159},    # Sarah Hilzendeger
    {"user_id": 205, "project_id": 53, "task_column_id": 280},  # Thomas Schrutt
    {"user_id": 23, "project_id": 18, "task_column_id": 109},   # Victor May
    {"user_id": 908, "project_id": 45, "task_column_id": 138},  # Vincent Bigioni
]

# Rapports business - pour les binômes commerciaux
# Format: liste d'user_ids par équipe
BUSINESS_REPORTS = [
    {"user_ids": [9, 695], "project_id": 25, "task_column_id": 126}, # Cameron x Khalil 
    {"user_ids": [909, 747], "project_id": 211, "task_column_id": 942}, # Darius x Adrien 
    {"user_ids": [218, 16], "project_id": 79, "task_column_id": 116}, # Justine x Amandine 
    {"user_ids": [23, 16], "project_id": 18, "task_column_id": 109}, # Victor x Amandine 
    {"user_ids": [863], "project_id": 189, "task_column_id": 844},  # Alexandre Schmitt
    {"user_ids": [862], "project_id": 190, "task_column_id": 848},  # Corentin Dumont
    {"user_ids": [17], "project_id": 45, "task_column_id": 138},   # Axel Aragoncillo
    {"user_ids": [13], "project_id": 20, "task_column_id": 112},   # Axel Lemarinier
    {"user_ids": [302], "project_id": 135, "task_column_id": 653},  # Hugo Wahl
    {"user_ids": [22], "project_id": 35, "task_column_id": 240},   # Louise Quintrand
    {"user_ids": [207], "project_id": 40, "task_column_id": 203},  # Maxime Guedou
    {"user_ids": [908], "project_id": 45, "task_column_id": 138},  # Vincent Bigioni
    # À configurer selon tes binômes commerciaux
    # Exemple: {"user_ids": [9, 862], "project_id": 151, "task_column_id": 756},  # Cameron + Corentin
]
