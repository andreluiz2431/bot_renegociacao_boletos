import json
import os
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Escopos para acessar o Google Calendar
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# Função para autenticar e acessar a API do Google Calendar
def autenticar_google_calendar():
    print("Iniciando autenticação no Google Calendar...")
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        print("Credenciais carregadas do token.json.")
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Token expirado. Atualizando...")
            creds.refresh(Request())
        else:
            print("Realizando autenticação inicial...")
            try:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                # Use o fluxo alternativo com `oob` para evitar bloqueio
                auth_url, _ = flow.authorization_url(prompt='consent')
                print(f"Por favor, acesse este URL e autorize o acesso:\n{auth_url}")
                code = input("Digite o código de autenticação fornecido: ")
                creds = flow.fetch_token(code=code)
            except Exception as e:
                print(f"Erro durante a autenticação: {e}")
                return None
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            print("Token salvo com sucesso.")
    return creds

# Função para buscar eventos e atualizar boletos.json
def atualizar_boletos_json():
    print("Iniciando atualização dos boletos...")
    creds = autenticar_google_calendar()
    service = build('calendar', 'v3', credentials=creds)

    now = datetime.utcnow().isoformat() + 'Z'
    past = (datetime.utcnow() - timedelta(days=30)).isoformat() + 'Z'

    print(f"Buscando eventos de {past} até {now}...")
    events_result = service.events().list(
        calendarId='primary', timeMin=past, timeMax=now, singleEvents=True, orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])

    if not events:
        print("Nenhum evento encontrado.")
        return

    boletos = []

    # Processar cada evento encontrado
    for event in events:
        titulo = event.get('summary', '')
        cor = event.get('colorId', '')
        print(f"Evento encontrado: {titulo} | Cor: {cor}")

        if titulo.startswith("Boleto"):
            try:
                _, nome, valor = titulo.split(" - ")
                valor = float(valor.replace(',', '.'))

                pago = cor in ['4', '7']  # CYAN (4) e YELLOW (7) são pagos
                status = "Pago" if pago else "Pendente"

                boleto = {
                    "nome": nome.strip(),
                    "valor": valor,
                    "pago": pago,
                    "cpf": ""  # CPF em branco por enquanto
                }
                boletos.append(boleto)

                print(f"Boleto processado: {boleto} | Status: {status}")

            except ValueError as e:
                print(f"Erro ao processar o evento '{titulo}': {e}")

    # Salvar boletos no arquivo boletos.json
    with open('boletos.json', 'w') as f:
        json.dump(boletos, f, indent=4, ensure_ascii=False)
        print("Arquivo boletos.json atualizado com sucesso.")

# Função para agendar a execução diária
def agendar_execucao_diaria():
    from apscheduler.schedulers.blocking import BlockingScheduler
    scheduler = BlockingScheduler()
    print("Executando atualização de boletos imediatamente para teste...")
    atualizar_boletos_json()  # Executa imediatamente para teste

    print("Agendando execução diária da atualização dos boletos...")
    scheduler.add_job(atualizar_boletos_json, 'interval', days=1)
    print("Agendamento iniciado. A função será executada uma vez por dia.")
    scheduler.start()

if __name__ == '__main__':
    agendar_execucao_diaria()
