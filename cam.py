import cv2
import time
import os
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import sys
import pyautogui
import numpy as np
from datetime import datetime

try:
    import pyscreeze
except ImportError as e:
    messagebox.showerror("Erreur", f"Erreur d'importation de pyscreeze : {e}")
    sys.exit(1)

# Modules conditionnels pour les différentes plateformes
try:
    import paramiko
except ImportError:
    paramiko = None

try:
    from pydrive.auth import GoogleAuth
    from pydrive.drive import GoogleDrive
except ImportError:
    GoogleAuth = None
    GoogleDrive = None

try:
    import dropbox
except ImportError:
    dropbox = None

# Fonction pour générer le chemin du répertoire en fonction de la date actuelle
def generate_directory_path():
    now = datetime.now()
    year = now.strftime("%Y")
    month = now.strftime("%m_%B")
    day = now.strftime("%d_%A")
    directory_path = os.path.join(year, month, day)
    return directory_path

def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)
    return path

# Fonction pour charger la configuration
def load_config():
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        config = {}
    return config

# Fonction pour sauvegarder la configuration
def save_config(config):
    with open('config.json', 'w') as f:
        json.dump(config, f)

# Fonction pour installer un package
def install_package(package_name):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])

# Classe pour gérer l'enregistrement vidéo avec l'interface Tkinter
class VideoRecorder:
    def __init__(self, root):
        self.root = root
        self.root.title("Enregistreur Vidéo")
        self.config = load_config()

        # Initialisation des onglets
        self.tab_control = ttk.Notebook(root)
        self.record_tab = ttk.Frame(self.tab_control)
        self.export_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.record_tab, text='Enregistrement')
        self.tab_control.add(self.export_tab, text='Multi Export')
        self.tab_control.pack(expand=1, fill='both')

        # Initialisation de l'interface Enregistrement
        self.init_record_tab()

        # Initialisation de l'interface Multi Export
        self.init_export_tab()

        # Initialisation de la caméra
        self.is_recording = False
        self.recording_thread = None
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            messagebox.showerror("Erreur", "Impossible d'ouvrir la caméra.")
            self.root.destroy()
            return

        self.frame_width = int(self.cap.get(3))
        self.frame_height = int(self.cap.get(4))
        self.fps = 20
        self.record_time = 10 * 60  # 10 minutes
        self.current_filename = None
        self.current_screen_filename = None

    def init_record_tab(self):
        """Initialisation de l'onglet Enregistrement."""
        frame = ttk.LabelFrame(self.record_tab, text="Contrôle de l'enregistrement")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.record_screen_var = tk.BooleanVar()
        tk.Checkbutton(frame, text="Enregistrer l'écran en simultané", variable=self.record_screen_var).pack(pady=10)

        self.start_button = tk.Button(frame, text="Démarrer Enregistrement", command=self.start_recording)
        self.start_button.pack(pady=10)

        self.stop_button = tk.Button(frame, text="Arrêter Enregistrement", command=self.stop_recording, state=tk.DISABLED)
        self.stop_button.pack(pady=10)

    def init_export_tab(self):
        """Initialisation de l'onglet Multi Export."""
        scroll_canvas = tk.Canvas(self.export_tab)
        scroll_frame = ttk.Frame(scroll_canvas)
        scroll_bar = ttk.Scrollbar(self.export_tab, orient="vertical", command=scroll_canvas.yview)
        scroll_canvas.configure(yscrollcommand=scroll_bar.set)

        scroll_bar.pack(side="right", fill="y")
        scroll_canvas.pack(side="left", fill="both", expand=True)
        scroll_canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        scroll_frame.bind("<Configure>", lambda e: scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all")))

        sections = [
            ("FTP", [("Hôte FTP", 'ftp_host', 50), ("Nom d'utilisateur FTP", 'ftp_username', 50),
                     ("Mot de passe FTP", 'ftp_password', 50, "*"), ("Chemin de destination FTP", 'ftp_destination', 50)]),
            ("Google Drive", [("ID du dossier Google Drive", 'gdrive_folder_id', 50)]),
            ("Dropbox", [("Token d'accès Dropbox", 'dropbox_token', 50)]),
            ("OneDrive", [("Client ID", 'onedrive_client_id', 50), ("Client Secret", 'onedrive_client_secret', 50, "*"), ("Tenant ID", 'onedrive_tenant_id', 50)]),
            ("Sync.com", [("Token Sync.com", 'sync_com_token', 50)]),
            ("Tresorit", [("Token Tresorit", 'tresorit_token', 50)]),
            ("Wasabi", [("Clé d'accès Wasabi", 'wasabi_access_key', 50), ("Clé secrète Wasabi", 'wasabi_secret_key', 50, "*")]),
            ("Mega", [("Email Mega", 'mega_email', 50), ("Mot de passe Mega", 'mega_password', 50, "*")]),
            ("Box", [("Token Box", 'box_token', 50)]),
        ]

        self.check_vars = {}

        for section_name, fields in sections:
            section_frame = ttk.LabelFrame(scroll_frame, text=section_name)
            section_frame.pack(fill="x", expand=True, padx=10, pady=5)

            for field in fields:
                if len(field) == 3:
                    label, var_name, width = field
                    show_char = ""
                else:
                    label, var_name, width, show_char = field

                var = tk.StringVar(value=self.config.get(var_name, ''))
                self.check_vars[var_name] = var
                ttk.Label(section_frame, text=label).pack(anchor="w", padx=5)
                tk.Entry(section_frame, textvariable=var, width=width, show=show_char).pack(fill="x", padx=5, pady=2)

            tk.Checkbutton(section_frame, text=f"Exporter vers {section_name}", variable=tk.BooleanVar()).pack(anchor="w", padx=5, pady=5)

        tk.Button(scroll_frame, text="Enregistrer les paramètres", command=self.save_export_settings).pack(pady=10)
        tk.Button(scroll_frame, text="Installer les packages requis", command=self.install_required_packages).pack(pady=10)

    def save_export_settings(self):
        """Enregistrer les paramètres d'exportation."""
        for var_name, var in self.check_vars.items():
            self.config[var_name] = var.get()
        save_config(self.config)
        messagebox.showinfo("Succès", "Paramètres enregistrés.")

    def install_required_packages(self):
        """Installation des packages requis pour les plateformes sélectionnées."""
        try:
            if paramiko is None:
                install_package('paramiko')
            if GoogleAuth is None:
                install_package('pydrive')
            if dropbox is None:
                install_package('dropbox')
            install_package('msal')  # Pour Microsoft OneDrive
            install_package('requests')  # Pour les requêtes HTTP
            install_package('pyautogui')  # Pour la capture d'écran
            messagebox.showinfo("Succès", "Tous les packages requis ont été installés.")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'installation des packages : {e}")

    def start_recording(self):
        """Démarrage de l'enregistrement vidéo."""
        if not self.is_recording:
            self.is_recording = True
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.recording_thread = threading.Thread(target=self.record_video)
            self.recording_thread.start()

    def stop_recording(self):
        """Arrêt de l'enregistrement vidéo."""
        if self.is_recording:
            self.is_recording = False
            self.recording_thread.join()  # Attendez que l'enregistrement se termine correctement
            if self.current_filename and os.path.exists(self.current_filename):
                if self.record_screen_var.get() and self.current_screen_filename and os.path.exists(self.current_screen_filename):
                    self.combine_videos(self.current_filename, self.current_screen_filename)
                self.export_files()
            else:
                messagebox.showerror("Erreur", "Le fichier vidéo n'a pas été trouvé pour l'exportation.")
            self.reset_interface()

    def reset_interface(self):
        """Réinitialise l'interface après l'arrêt de l'enregistrement."""
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.current_filename = None
        self.current_screen_filename = None

    def record_video(self):
        """Enregistre la vidéo à partir de la caméra et, optionnellement, l'écran."""
        try:
            directory_path = generate_directory_path()
            create_directory(directory_path)

            timestamp = time.strftime("%Hh%M_%S")
            self.current_filename = os.path.join(directory_path, f"{timestamp}.avi")
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            out = cv2.VideoWriter(self.current_filename, fourcc, self.fps, (self.frame_width, self.frame_height))

            if self.record_screen_var.get():
                self.current_screen_filename = os.path.join(directory_path, f"{timestamp}_screen.avi")
                screen_size = pyautogui.size()
                screen_out = cv2.VideoWriter(self.current_screen_filename, fourcc, self.fps, screen_size)

            start_time = time.time()
            while self.is_recording and (time.time() - start_time) <= self.record_time:
                ret, frame = self.cap.read()
                if ret:
                    out.write(frame)
                    if self.record_screen_var.get():
                        screen_frame = pyautogui.screenshot()
                        screen_frame = cv2.cvtColor(np.array(screen_frame), cv2.COLOR_RGB2BGR)
                        screen_out.write(screen_frame)
                else:
                    messagebox.showerror("Erreur", "Impossible de lire l'image.")
                    break

            out.release()
            if self.record_screen_var.get():
                screen_out.release()

            messagebox.showinfo("Information", f"Enregistrement terminé : {self.current_filename}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'enregistrement : {e}")
        finally:
            self.is_recording = False

    def combine_videos(self, video1_path, video2_path):
        """Combine la vidéo de la caméra avec la vidéo de l'écran."""
        try:
            cap1 = cv2.VideoCapture(video1_path)
            cap2 = cv2.VideoCapture(video2_path)

            frame_width = int(cap1.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap1.get(cv2.CAP_PROP_FRAME_HEIGHT))
            small_width = int(frame_width / 4)
            small_height = int(frame_height / 4)

            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            output_path = video1_path.replace('.avi', '_combined.avi')
            out = cv2.VideoWriter(output_path, fourcc, self.fps, (frame_width, frame_height))

            while True:
                ret1, frame1 = cap1.read()
                ret2, frame2 = cap2.read()

                if not ret1 or not ret2:
                    break

                frame2_resized = cv2.resize(frame2, (small_width, small_height))
                frame1[-small_height:, -small_width:] = frame2_resized

                out.write(frame1)

            cap1.release()
            cap2.release()
            out.release()

            messagebox.showinfo("Succès", f"Vidéo combinée créée : {output_path}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de la combinaison des vidéos : {e}")

    def export_files(self):
        """Exporte les fichiers vers les destinations configurées."""
        # Implémentez les fonctions d'exportation pour chaque service ici
        pass

    def on_closing(self):
        """Actions à effectuer lors de la fermeture de l'application."""
        self.stop_recording()
        if self.cap.isOpened():
            self.cap.release()
        self.root.destroy()

# Création de l'interface Tkinter
root = tk.Tk()
root.geometry("800x600")  # Redimensionnement automatique
video_recorder = VideoRecorder(root)
root.protocol("WM_DELETE_WINDOW", video_recorder.on_closing)
root.mainloop()

