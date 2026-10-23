from getpass import getpass
from app.live.auth import hash_password

if __name__ == "__main__":
    password = getpass("Nova senha do operador (mínimo 12 caracteres): ")
    confirmation = getpass("Confirme: ")
    if password != confirmation:
        raise SystemExit("As senhas não coincidem.")
    print(hash_password(password))
