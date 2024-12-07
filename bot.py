from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv
import os
import json

# Carrega as variáveis do arquivo .env
load_dotenv()

# Obtém o token do ambiente
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not TOKEN:
    raise ValueError("O token do bot não foi encontrado. Verifique seu arquivo .env.")

# Carregar boletos de um arquivo JSON
#def carregar_boletos():
#    with open('boletos.json', 'r') as file:
#        return json.load(file)

# Carregar boletos de uma variável de ambiente
def carregar_boletos():
    boletos_json = os.getenv('BOLETOS_JSON')
    if not boletos_json:
        raise ValueError("Boletos JSON não encontrado. Verifique as variáveis de ambiente.")
    return json.loads(boletos_json)

# Função para calcular multa e juros
def calcular_multa_juros(valor, dias_vencidos):
    multa = 0.05 * valor  # 5% de multa
    juros = 0.0033 * dias_vencidos * valor  # 0,33% ao dia
    return valor + multa + juros

# Função para calcular o número de parcelas
def calcular_parcelas(total_divida):
    max_parcelas = int(total_divida // 100)  # Cada parcela deve ser no mínimo R$ 100,00
    if total_divida < 100:
        return 1  # Se a dívida for menor que R$ 100, permitir 1 parcela
    return max_parcelas

# Função para calcular custo adicional para boletos vencidos há mais de 30 dias
def calcular_custo_adicional_boletos(boletos_vencidos):
    custo_adicional = 0
    hoje = datetime.now()
    
    for boleto in boletos_vencidos:
        vencimento = datetime.strptime(boleto['vencimento'], '%Y-%m-%d')
        dias_vencidos = (hoje - vencimento).days
        
        if dias_vencidos >= 60:
            custo_adicional += 10  # Adiciona R$ 10,00 por boleto vencido há mais de 60 dias
        elif dias_vencidos >= 30:
            custo_adicional += 6  # Adiciona R$ 6,00 por boleto vencido há mais de 30 dias

    return custo_adicional

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Olá! Digite seu nome para verificar suas pendências.')
    context.user_data.clear()  # Limpa dados anteriores

# Função para verificar boletos pelo NOME ou CPF
async def verificar_boletos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    entrada = update.message.text
    boletos_data = carregar_boletos()

    # Verificar se estamos esperando um CPF
    if 'clientes_pendentes' in context.user_data:
        clientes_pendentes = context.user_data['clientes_pendentes']
        cliente = next((cliente for cliente in clientes_pendentes if cliente['cpf'] == entrada), None)

        if not cliente:
            await update.message.reply_text('CPF não encontrado. Verifique e tente novamente.')
            return
    else:
        # Buscar clientes pelo nome (sem diferenciar maiúsculas/minúsculas)
        nome = entrada.lower()
        clientes_encontrados = [cliente for cliente in boletos_data if nome in cliente['cliente'].lower()]

        if not clientes_encontrados:
            await update.message.reply_text('Nome não encontrado. Verifique e tente novamente.')
            return

        if len(clientes_encontrados) > 1:
            await update.message.reply_text(
                "Foram encontrados vários clientes com esse nome. Por favor, informe seu CPF para prosseguir."
            )
            context.user_data['clientes_pendentes'] = clientes_encontrados
            return

        # Caso apenas um cliente seja encontrado
        cliente = clientes_encontrados[0]

    # Limpar dados temporários
    context.user_data.pop('clientes_pendentes', None)

    context.user_data['cliente'] = cliente['cliente']

    boletos = cliente['boletos']
    boletos_vencidos = []
    boletos_ativos = []
    total_vencidos = 0
    hoje = datetime.now()

    for boleto in boletos:
        vencimento = datetime.strptime(boleto['vencimento'], '%Y-%m-%d')
        if not boleto['pago']:
            if vencimento < hoje:
                dias_vencidos = (hoje - vencimento).days
                boleto['valor_corrigido'] = calcular_multa_juros(boleto['valor'], dias_vencidos)
                boletos_vencidos.append(boleto)
                total_vencidos += boleto['valor_corrigido']
            else:
                boletos_ativos.append(boleto)
    mensagem = f"Nome do cliente: {cliente['cliente']}"

    mensagem += "📋 Boletos Ativos:\n"
    for boleto in boletos_ativos:
        mensagem += f"- ID: {boleto['id']}, Valor: R$ {boleto['valor']:.2f}, Vencimento: {boleto['vencimento']}\n"

    mensagem += "\n⚠️ Boletos Vencidos:\n"
    for boleto in boletos_vencidos:
        mensagem += (
            f"- ID: {boleto['id']}, Valor Original: R$ {boleto['valor']:.2f}, "
            f"Valor Corrigido: R$ {boleto['valor_corrigido']:.2f}, Vencimento: {boleto['vencimento']}\n"
        )

    custo_adicional = calcular_custo_adicional_boletos(boletos_vencidos)
    total_divida = total_vencidos + custo_adicional
    max_parcelas = calcular_parcelas(total_divida)

    mensagem += (
        f"\n📌 Total Vencido (com multa e juros): R$ {total_vencidos:.2f}\n"
        f"Adicional de R$ 10,00 por cada boleto vencido há mais de 60 dias: R$ {custo_adicional:.2f}\n"
        f"\n Total a pagar: R$ {total_divida:.2f}\n"
    )

    if max_parcelas == 1:
        mensagem += "Você deve pagar o valor em uma única parcela.\n"
    else:
        mensagem += f"Você pode parcelar em até {max_parcelas} vezes.\n"

    mensagem += "Digite /renegociar X para escolher o número de parcelas desejado (X)."

    await update.message.reply_text(mensagem)

    context.user_data['total_divida'] = total_divida
    context.user_data['max_parcelas'] = max_parcelas

# Função para renegociar com um número específico de parcelas
async def renegociar_divida(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Use o comando /renegociar X, onde X é o número de parcelas desejadas.")
        return

    parcelas = int(args[0])
    total_divida = context.user_data.get('total_divida')
    max_parcelas = context.user_data.get('max_parcelas')

    if not total_divida or not max_parcelas:
        await update.message.reply_text("Erro ao recuperar a dívida. Verifique seu nome novamente.")
        return

    if parcelas < 1 or parcelas > max_parcelas:
        await update.message.reply_text(f"Você pode parcelar em até {max_parcelas} vezes.")
        return

    context.user_data['parcelas'] = parcelas
    valor_parcela = total_divida / parcelas

    await update.message.reply_text(
        f"Você escolheu {parcelas} parcelas. Cada parcela será de R$ {valor_parcela:.2f}.\n"
        "Agora escolha a forma de pagamento usando o comando /pagamento X (onde X pode ser pix, cartão ou boleto)."
    )

# Função para processar a escolha da forma de pagamento via comando /pagamento
async def escolher_forma_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args:
        await update.message.reply_text("Use o comando /pagamento X, onde X pode ser pix, cartão ou boleto.")
        return

    forma_pagamento = args[0].lower()
    parcelas = context.user_data['parcelas']
    total_divida = context.user_data['total_divida']

    if forma_pagamento == 'pix':
        await update.message.reply_text(
            f"O valor total da dívida é R$ {total_divida:.2f}. Por favor, pague via Pix e envie o comprovante."
        )
    elif forma_pagamento == 'cartão':
        valor_parcela = total_divida / parcelas
        await update.message.reply_text(
            f"Você escolheu {parcelas} parcelas no cartão. Cada parcela será de R$ {valor_parcela:.2f}. "
            "Compareça à loja ou entre em contato para concluir a transação."
        )
    elif forma_pagamento == 'boleto':
        valor_parcela = (total_divida / parcelas) + 3.00  # Exemplo de taxa adicional por boleto
        await update.message.reply_text(
            f"Você escolheu {parcelas} parcelas no boleto. Cada parcela será de R$ {valor_parcela:.2f}. "
            "Os boletos serão enviados em breve."
        )
    else:
        await update.message.reply_text("Forma de pagamento inválida. Escolha entre pix, cartão ou boleto.")

def main() -> None:
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, verificar_boletos))
    application.add_handler(CommandHandler("renegociar", renegociar_divida))
    application.add_handler(CommandHandler("pagamento", escolher_forma_pagamento))

    application.run_polling()

if __name__ == "__main__":
    main()