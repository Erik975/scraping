from http.server import SimpleHTTPRequestHandler, HTTPServer
import socket
import datetime
import os

class VerboseHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] {self.address_string()} - {format % args}")

    def do_GET(self):
        self.log_message("Requête GET reçue: chemin=%s", self.path)
        self.log_message("Headers reçus:")
        for key, value in self.headers.items():
            self.log_message("  %s: %s", key, value)

        # Si la racine "/" est demandée, servir index.html explicitement
        if self.path == "/":
            self.path = "/index.html"

        # Appeler la méthode de base pour servir le fichier
        try:
            super().do_GET()
            self.log_message("Fichier servi avec succès : %s", self.path)
        except Exception as e:
            self.log_message("Erreur lors du service du fichier %s : %s", self.path, e)
            self.send_error(404, "Fichier non trouvé")

def run_server_on_random_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    server_address = ("", port)
    httpd = HTTPServer(server_address, VerboseHandler)

    print(f"[INFO] Démarrage du serveur HTTP sur le port {port}")
    print(f"[INFO] Ctrl+C pour arrêter.")
    print(f"[INFO] Servira index.html à la racine '/'")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Arrêt demandé, fermeture du serveur...")
        httpd.server_close()
        print("[INFO] Serveur arrêté proprement.")

if __name__ == "__main__":
    run_server_on_random_port()
