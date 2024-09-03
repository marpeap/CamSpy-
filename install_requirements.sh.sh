#!/bin/bash

echo "Installation des dépendances requises..."

# Mettre à jour pip
pip install --upgrade pip

# Installer les bibliothèques Python nécessaires
pip install pyautogui
pip install opencv-python
pip install numpy
pip install msal
pip install requests
pip install Pillow  # Pour gérer les captures d'écran avec pyautogui

# Installation des bibliothèques conditionnelles
pip install paramiko
pip install pydrive
pip install dropbox

echo "Installation terminée."

