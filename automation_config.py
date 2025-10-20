"""
Configuration pour les rapports automatiques hebdomadaires.
Modifie ce fichier pour ajouter/retirer des utilisateurs ou changer les destinations.
"""

# Rapports d'activité - un rapport par utilisateur
ACTIVITY_REPORTS = [
    {"user_id": 747, "project_id": 211, "task_column_id": 942},  # Adrien Massart-Lambert
    {"user_id": 21, "project_id": 151, "task_column_id": 726},   # Agathe Férat
    {"user_id": 7, "project_id": 158, "task_column_id": 726},    # Alcides De Oliveira Guerra
    {"user_id": 863, "project_id": 151, "task_column_id": 726},  # Alexandre Schmitt
    {"user_id": 19, "project_id": 151, "task_column_id": 726},   # Alexis Vienot
    {"user_id": 16, "project_id": 151, "task_column_id": 726},   # Amandine Aubry
    {"user_id": 208, "project_id": 151, "task_column_id": 726},  # Antoine Hemmerlé
    {"user_id": 15, "project_id": 151, "task_column_id": 726},   # Antoine Payet
    {"user_id": 701, "project_id": 151, "task_column_id": 726},  # Antonina Onishchenko
    {"user_id": 17, "project_id": 151, "task_column_id": 726},   # Axel Aragoncillo
    {"user_id": 13, "project_id": 151, "task_column_id": 726},   # Axel Lemarinier
    {"user_id": 784, "project_id": 151, "task_column_id": 726},  # Budoc Doan
    {"user_id": 9, "project_id": 25, "task_column_id": 126},    # Cameron Price
    {"user_id": 537, "project_id": 151, "task_column_id": 726},  # Carla Rodriguez
    {"user_id": 862, "project_id": 151, "task_column_id": 726},  # Corentin Dumont
    {"user_id": 212, "project_id": 151, "task_column_id": 726},  # Daniel Bonifassi
    {"user_id": 909, "project_id": 211, "task_column_id": 942},  # Darius Pautrat
    {"user_id": 211, "project_id": 151, "task_column_id": 726},  # Emeric Acker
    {"user_id": 770, "project_id": 151, "task_column_id": 726},  # Erika Runser
    {"user_id": 464, "project_id": 151, "task_column_id": 726},  # Fleur Kornmann
    {"user_id": 215, "project_id": 151, "task_column_id": 726},  # Hubert Herphelin
    {"user_id": 302, "project_id": 151, "task_column_id": 726},  # Hugo Wahl
    {"user_id": 703, "project_id": 151, "task_column_id": 726},  # Inès Vedrenne
    {"user_id": 206, "project_id": 151, "task_column_id": 726},  # Jean Dietrich
    {"user_id": 218, "project_id": 151, "task_column_id": 726},  # Justine Clément
    {"user_id": 695, "project_id": 25, "task_column_id": 126},  # Khalil Eddine Djerbi
    {"user_id": 709, "project_id": 151, "task_column_id": 726},  # Lancelot Minoggio
    {"user_id": 22, "project_id": 151, "task_column_id": 726},   # Louise Quintrand
    {"user_id": 216, "project_id": 151, "task_column_id": 726},  # Manon David
    {"user_id": 843, "project_id": 151, "task_column_id": 726},  # Marie Bedin
    {"user_id": 786, "project_id": 158, "task_column_id": 726},  # Mattis Almeida Lima
    {"user_id": 207, "project_id": 151, "task_column_id": 726},  # Maxime Guedou
    {"user_id": 771, "project_id": 151, "task_column_id": 726},  # Océane Chappuis
    {"user_id": 8, "project_id": 151, "task_column_id": 726},    # Pierre Dietrich
    {"user_id": 6, "project_id": 151, "task_column_id": 726},    # Sarah Hilzendeger
    {"user_id": 205, "project_id": 151, "task_column_id": 726},  # Thomas Schrutt
    {"user_id": 23, "project_id": 151, "task_column_id": 726},   # Victor May
    {"user_id": 908, "project_id": 151, "task_column_id": 726},  # Vincent Bigioni
]

# Rapports business - pour les binômes commerciaux
# Format: liste d'user_ids par équipe
BUSINESS_REPORTS = [
    # À configurer selon tes binômes commerciaux
    # Exemple: {"user_ids": [9, 862], "project_id": 151, "task_column_id": 756},  # Cameron + Corentin
]