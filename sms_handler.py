#!venv/bin/python
from flask import Flask, request, redirect
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client

# bitcoin wallet code
import ecdsa
import coinapult
from coinapult import CoinapultClient
cli = coinapult.CoinapultClient()
cli.createAccount()
cli.activateAccount(agree = True)
COINAPULT_CONST = 0.0001

app = Flask(__name__)

phone_to_btc = {}
btc_to_phone = {}
btc_to_balance = {} # in satoshis

# starting amount in new user wallet (testing purposes)
SATOSHI_START_CONSTANT = 123456789

# Twilio API details
account_sid = "XXXXXXXXXXXXXXXXXXXXXXXXXX"
auth_token  = "XXXXXXXXXXXXXXXXXXXXXXXXX"
client = Client(account_sid, auth_token)


@app.route("/receive_sms", methods=['GET', 'POST'])
def sms_reply():
    body = str(request.form['Body'])
    phone_number = str(request.form['From'])

    # handle new users
    if(phone_number not in phone_to_btc):
        response = handle_new_user(phone_number)
    # process commands
    else:
        first_word = body.split()[0]
        switcher = {
            "helpme": help_command,
            "bal": bal_command,
            "addr": addr_command,
            "pay": pay_command,
            "request": request_command
        }
        command = switcher.get(first_word.lower(), lambda: "Invalid command")
        response = command(phone_number, body.split())

    # create response
    resp = MessagingResponse()
    resp.message(response)
    return str(resp)

def handle_new_user(phone_number):
    new_address = get_new_address(phone_number)
    phone_to_btc[phone_number] = new_address
    btc_to_phone[new_address] = phone_number
    btc_to_balance[new_address] = SATOSHI_START_CONSTANT
    return ("Welcome to BitSMS! Your new BTC address is %s. Type in helpme to view commands" % (new_address))

def help_command(phone_number, body):
    return '''Here are the available commands:
    helpme - ask for help,
    bal - check your balance,
    addr - neceive your bitcoin address,
    pay - pay bitcoins to another phone number or bitcoin address,
    request - request bitcoins from another phone number
    '''

def bal_command(phone_number, words):
    balance = sat_to_btc(get_balance(phone_number))
    return ("Balance: %s btc" % (balance))

def addr_command(phone_number, words):
    return ("Your Bitcoin address is: %s" % (phone_to_btc[phone_number]))

# command format is 'pay {-b btc_address, -p phone_number} btc_amount'
def pay_command(phone_number, words):
    balance = sat_to_btc(get_balance(phone_number))
    pay_amount = float(words[3])

    # not enough money
    if (balance < pay_amount):
        return ("Error: Your balance of %f btc is insufficient" % (balance))

    payTo = words[2]
    payType = words[1]
    from_btc_addr = phone_to_btc[phone_number]
    # paying a phone number
    if(payType == "-p"):
        pay_amount_sat = btc_to_sat(pay_amount)
        # handle paying new phone number
        if payTo not in phone_to_btc:
            message = client.messages.create(to=payTo, from_="+16692227988", body=handle_new_user(payTo))
        btc_to_balance[from_btc_addr] = btc_to_balance[from_btc_addr] - pay_amount_sat
        to_btc_addr = phone_to_btc[payTo]
        btc_to_balance[to_btc_addr] = btc_to_balance[to_btc_addr] + pay_amount_sat
        curr_balance = sat_to_btc(btc_to_balance[from_btc_addr])
        alert_payment_received(payTo, phone_number, pay_amount)
        return ("Successfully paid %f btc to %s. Your balance is now %f btc" % (pay_amount, payTo, curr_balance))

    # otherwise paying a btc address
    elif(payType == '-b'):
        btc_external_tx(pay_amount, payTo)

def request_command(phone_number, words):
    return "Request command not implemented yet"

def get_new_address(phone_number):
    #return 'btc_' + str(phone_number)
    cli_response = cli.receive(COINAPULT_CONST, currency="BTC", refreshOnExpire=True, callback="www.downcloud.io/receive_callback")
    btc_address = cli_response['address']
    return btc_address

def get_balance(phone_number):
    btc_address = phone_to_btc[phone_number]
    balance = btc_to_balance[btc_address]
    return balance

def sat_to_btc(sat):
    return sat / 100000000.0

def btc_to_sat(btc):
    return btc * 100000000.0

def alert_payment_received(payTo, payFrom, pay_amount):
    curr_balance = sat_to_btc(btc_to_balance[phone_to_btc[payTo]])
    textBody = ("%s has paid you %f btc. Your balance is now %f btc" % (payFrom, pay_amount, curr_balance))
    message = client.messages.create(to=payTo, from_="+16692227988", body=textBody)

def btc_external_tx(amount, address):
    cli.send(amount, address)


@app.route("/receive_callback", methods=['GET', 'POST'])
def receive_callbac():
    address = request.form['Address']
    key = list(btc_to_phone.keys())[0]
    btc_to_balance[key] = btc_to_balance[key] + btc_to_sat(COINAPULT_CONST)
    toNum = btc_to_phone[key]
    textBody = ("You got paid %f btc" % (COINAPULT_CONST))
    message = client.messages.create(to=toNum, from_="+16692227988", body=textBody)
    return ""


@app.route("/hello", methods=['GET', 'POST'])
def hello():
    print "heloooooo"
    return str("hello")

if __name__ == "__main__":
    app.run(debug=True)
