### EMAIL CODE FOR AUTOMATON

import smtplib
from email.MIMEText import MIMEText
from email.MIMEMultipart import MIMEMultipart

def setServer(sender, smtp, password):
    try:
        server = smtplib.SMTP(smtp)
        #server.connect
        server.ehlo()
        server.starttls()
        server.set_debuglevel(True)
        server.login(str(sender), str(password))
        message = "Here is your server obj"
        return {"message": message, "server": server, "status": "success"}
    except Exception as e:
        return{"message": str(e), "server": None, "status": "fail"}

def sendMessage(sender, smtp, password, reciever, missive, server):
    try:
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = receiver
        msg['Subject'] = "Automaton Error"
        try:
            body = missive
        except:
            body = "Error sending message."
        msg.attach(MIMEText(body, 'plain'))
        server.sendmail(sender, reciever, msg.as_string())
        server.quit()
    except Exception as e:
        return {"status": "fail", "message": str(e)}

def main(sender, smtp, password, reciever, missive):
    try:
        response = setServer(sender, smtp, password)
        print response['message']
        server = response['server']
    except Exception as e:
        print "There was an error logging in to the email"
        print str(e)
        server.quit()
        return {"message": str(e), "status": "fail"}
    try:
        response = sendMessage(sender, smtp, password, reciever, missive, server)
    except Exception as e:
        print "There was an error sending the email"
        print str(e)
        server.quit()
        return {"message": str(e), "status": "fail"}
    return {"message": "Email sent", "status": "success"}