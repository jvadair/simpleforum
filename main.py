# TODO: better mobile site, split pages into 50msgs per page, password recovery, spam detection, claiming forumns, request deletion, account pages, login on multiple devices (multiple tokens), save session data on reboot

from flask import Flask, render_template, request, session, send_from_directory, redirect, abort
from werkzeug.utils import secure_filename
import os
from sendmail import send_verification_code, send_thread_notif
from html import escape
# from datamanager import DataManager
from pyndb import PYNDatabase
from datetime import datetime as dt
import random
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
app = Flask(__name__)
pydb = PYNDatabase('forum.pyndb', filetype='plaintext')
logindb = PYNDatabase('login.pyndb', filetype='plaintext')
maildb = PYNDatabase('mailing_list.pyndb', filetype='plaintext')
months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
global_temp_codes = {}

VERIFIED_USERS = ('jva', 'jvadair', 'Arrows', 'SimpleForum')
DEVELOPERS = ('jva', 'jvadair')
EARLY_USERS = ('jva', 'jvadair', 'Arrows')
EXEMPLARY = ('jva', 'jvadair')
PROTECTED_CHANNELS = ('updates',)


def eval_block(block):
    if block.startswith('b'):
        block = block.replace('b[', '<b>')
        block = block.replace(']', '</b>')

    elif block.startswith('i'):
        block = block.replace('i[', '<i>')
        block = block.replace(']', '</i>')

    elif block.startswith('c'):
        block = block[2:]  # removes the c[ at the beginning
        blocksplit = block.split(', ')
        color = blocksplit[0]
        # splits the remaining text into arguments separated by commas,
        # the first argument should be a color,
        # and the second should be the text.
        block = f'<span style="color:{color}">'
        block += ', '.join(blocksplit[1:]) # removes the color argument from the text. also doesnt remove other text separated by commas.
        block = block.replace(']', '</span>')
        # print(block)

    elif block.startswith('l'):
        block = block.replace('l[', '<span style="font-size:150%">')
        block = block.replace(']', '</span>')

    elif block.startswith('p'):
        block = block.replace('p[', '')
        block = block.replace(']', '')
        block = f'<img src={block}>'

    return block

def startswithany(text, *args):
    for arg in args:
        if text.startswith(arg):
            return True

def endswithany(text, *args):
    for arg in args:
        if text.endswith(arg):
            return True

def hyperlink(message):
    message = message.split(' ')
    for word in message:
        if startswithany(word, 'http://', 'https://', 'www.', 'ww6.'):
            message[message.index(word)] = f'<a href="{word}">{word}</a>'
        elif endswithany(word, '.com', '.org', '.net', '.gov', '.io', '.ly', '.co', '.tv', '.live', '.tk'):
            message[message.index(word)] = f'<a href="https://{word}">{word}</a>'
    return ' '.join(message)

def _format(text):
    text = hyperlink(text)
    try:
        output = ''
        current_text = text
        for letter in text:
            if letter == '[':
                current_index = current_text.index('[')
                end_index = current_text.index(']')
                output += current_text[:current_index-1]
                block = current_text[current_index-1:end_index+1]
                try:
                    if current_text[current_index-2] == '/':
                        output = output[:len(output)-1]
                        output += block
                    else:
                        output += eval_block(block)
                except:
                    output += block
                    # uses plain text if there are any errors in the format
                current_text = current_text[end_index+1:]
        output += current_text
        return output

    except:
        return text
        # Returns text if there are any errors in the syntax

def loadforum(forum):
    output = ''
    forumval = eval(repr(pydb.get(forum).val))
    # print(forumval)
    if not forumval:
        forumval = [{'author': 'No posts yet...', 'time': 'N/A', 'message': "It's deadly silent here. Hey, is that a cobweb?"}]
    for item in forumval:
        output += "<div class='item'>\n"
        output += "<div class='meta'>\n"
        if item['author'].startswith('unverified$$'):
            item['author'] = item['author'].split('$$')[1]
            output += f"<h1 class='author_unverified'>{item['author']}</h1>\n"
        else:
            output += f"<h1 class='author'>{item['author']}</h1>\n"


            if item['author'] in VERIFIED_USERS:
                verified = True
            else:
                verified = False
            if item['author'] in DEVELOPERS:
                developer = True
            else:
                developer = False
            if item['author'] in EARLY_USERS:
                early = True
            else:
                early = False
            if item['author'] in EXEMPLARY:
                exemplary = True
            else:
                exemplary = False

            if verified or developer or early or exemplary:
                output += '<div class="badges">\n'
                if verified:
                    output += '<img src="https://simpleforum.jvadair.com/badge/verified.png" height="32px">\n'
                if developer:
                    output += '<img src="https://simpleforum.jvadair.com/badge/developer.png" height="32px">\n'
                if exemplary:
                    output += '<img src="https://simpleforum.jvadair.com/badge/exemplary.png" height="32px">\n'
                if early:
                    output += '<img src="https://simpleforum.jvadair.com/badge/early.png" height="32px">\n'
                output += '</div>'
        output += f"<h2 class='time'>{item['time']}</h2>\n"
        output += "</div>\n"
        output += f"<p class='message'>{item['message']}</p>\n"
        output += "</div>\n"
    return output

def process_login(data):
    if data['auth_type'] == 'login':
        if data['username'] not in logindb.all_usernames.val:
            return "We couldn't find that user in our database."
        for user in logindb.logins.val:
            if list(user.keys()) == [data['username']]:
                val = list(user.values())[0]
                if val['password'] == data['password']:
                    return False
                else:
                    return 'Wrong password, try again!'
    elif data['auth_type'] == 'signup':
        username = data['username']
        password = data['password']
        entered_email = data['email']
        if '@' not in entered_email or '.' not in entered_email:
            return 'Please enter a valid email'
        elif username in logindb.all_usernames.val:
            return 'Username is taken.'
        elif entered_email in logindb.all_emails.val:
            return 'Email is taken.'
        elif not password:
            return 'Please enter a password'
        elif len(username) < 2:
            return 'Your username must be at least 2 characters in length.'
        elif len(username) > 35:
            return 'Your username cannot be longer than 35 characters.'
        else:
            return False
    else:
        return 'Invalid auth type...?'

def errorpage(error):
    return render_template('error.html', error=error)

def log(message):
    print(get_time() + ' | ' + message)

def get_time():
    month = months[int(dt.now().strftime('%m'))-1]
    day = dt.now().strftime('%d')
    hour = int(dt.now().strftime('%H'))
    if hour > 12:
        hour = str(hour-12)
        ampm = 'PM'
    else:
        hour = str(hour)
        ampm = 'AM'
    if hour == '0':
        hour='12'
    minute = dt.now().strftime('%M')
    ftime = f"{month} {day} at {hour}:{minute}{ampm}"
    return ftime

def check_login_state():
    try:
        if session['logged_in']:
            if global_temp_codes[session['username']] == session['login_temp']:
                logged_in = session['username']
            else:
                session['logged_in'] = False
                logged_in = 'expired'
        else:
            logged_in = False
    except KeyError:
        logged_in = False

    return logged_in

@app.route("/<forum>")
def fixpath(forum):
    if len(forum) < 3:
        return errorpage('The forum name must be at least 3 characters in length.')
    if forum != forum.lower():
        return redirect(f'/{forum.lower()}/view', 302)
    return redirect(f'/{forum}/view', 302)

@app.route('/s')
def lsredirect():
    return redirect('/s/signup', 302)

@app.route('/s/<auth_type>')
def login(auth_type):
    auth_type = auth_type.lower()
    if auth_type == 'logout':
        logged_in = check_login_state()
        if not logged_in:
            return errorpage('You are not logged in. (Your login may have expired)')
        if logged_in == 'expired':
            return errorpage('Login expired.')
        del global_temp_codes[session['username']]
        log(f'AUTH | {session["username"]} has logged out')
        del session['username']
        del session['login_temp']
        del session['logged_in']
        return redirect('/', 302)
    if auth_type not in ('login', 'signup'):
        return redirect('/s/signup', 302)
    emailyn = '<input type="text" name="email" placeholder="Email">' if auth_type == 'signup' else ''
    if auth_type == 'login':
        title = 'Login'
    elif auth_type == 'signup':
        title = 'Sign Up'
    return render_template('auth.html', title=title, emailyn=emailyn, auth_type=auth_type)

@app.route('/s/postcredentials', methods=['POST'])
def authsession():
    data = dict(request.form)
    login_failed = process_login(data)
    if login_failed:
        return errorpage(login_failed)
    else:
        if data['auth_type'] == 'signup':
            vcode = '0'
            while vcode in logindb.all_verification_codes.val.keys():
                vcode = str(random.randint(100000,500000))
            send_verification_code(data['email'], data['username'], vcode)
            new_queue = logindb.logins_queue.val
            all_verification_codes = logindb.all_verification_codes.val
            all_emails = logindb.all_emails.val
            all_usernames = logindb.all_usernames.val
            new_queue.append({data['username']:{'verification_code':vcode, 'email':data['email'], 'password':data['password'], 'signup_date':dt.now().strftime('%m/%d/%Y')}})
            all_verification_codes[vcode] = data['username']
            all_emails.append(data['email'])
            all_usernames.append(data['username'])
            logindb.set('logins_queue', new_queue)
            logindb.set('all_verification_codes', all_verification_codes)
            logindb.set('all_emails', all_emails)
            logindb.set('all_usernames', all_usernames)
            logindb.save()
            log(f'AUTH | {data["username"]} has signed up')
            return render_template('pleaseverify.html')
        elif data['auth_type'] == 'login':
            temp_code = random.randint(0, 1000000)  # 0 to 1mil
            global_temp_codes[data['username']] = temp_code
            session['username'] = data['username']
            session['login_temp'] = temp_code
            session['logged_in'] = True
            log(f'AUTH | {data["username"]} has logged in')
            return redirect(data['redirect'], 302)
@app.route('/a')
def accredirect():
    return 'OK'

@app.route('/v/<vcode>')
def verification(vcode):
    queue = logindb.logins_queue.val
    logins = logindb.logins.val
    vcode_list = logindb.all_verification_codes.val
    if vcode in vcode_list.keys() and vcode != '0':
        username = vcode_list[vcode]
        for user in queue:
            if list(user.keys()) == [username]:
                userinfo = queue.index(user)
        userinfo = queue.pop(userinfo)
        del userinfo[username]['verification_code']
        logins.append(userinfo)
        del vcode_list[vcode]
        logindb.set('logins_queue', queue)
        logindb.set('all_verification_codes', vcode_list)
        logindb.set('logins', logins)
        logindb.save()
        log(f'AUTH | {username} has verified')
        return render_template('verified.html', username=username)
    else:
        return errorpage('Theres nobody with that verification code! (It may have expired)')

@app.route('/')
def rerout():
    return render_template('landing.html')

@app.errorhandler(404)
def page_not_found(e):
    return errorpage('That page couldn\'t be found...')

@app.errorhandler(500)
def server_error(e):
    log(f'ERROR | {e}')
    return errorpage('Our bad. We\'re not sure what went wrong, but please chat with us <a href="/bugreporting" style="color: #34eb80">here</a> if possible to let us know!')

@app.route("/<forum>/view")
def main(forum):
    if len(forum) < 3:
        return errorpage('The forum name must be at least 3 characters in length.')
    elif forum != forum.lower():
        return redirect(f'/{forum.lower()}/view', 302)
    try:
        pydb.get(forum).val
    except AttributeError:
        pydb.set(forum, [])
        pydb.save()
    # print(loadforum(data))
    try:
        if session['logged_in']:
            emailyn = session['username'] in maildb.forums.get(forum).val
        else:
            emailyn = 'not_logged_in'
    except (KeyError, AttributeError) as E:
        if type(E) is KeyError:
            emailyn = 'not_logged_in'
        elif type(E) is AttributeError:
            maildb.forums.create(forum, val=[])
            maildb.save()
            emailyn = session['username'] in maildb.forums.get(forum).val
    return render_template('index.html', content=loadforum(forum), title=forum, email_notifs=emailyn)
    # return '<h1>Redirecting...</h1><p>If this doesn\'t work, that would suck :/'

@app.route('/<forum>/postapi', methods=['POST'])
def api(forum):
    data = dict(request.form)
    logged_in = check_login_state()
    if logged_in == 'expired':
        return errorpage('Login has expired.')
    elif logged_in:
        data['author'] = logged_in

    # data = request.data.decode()
    # print(repr(data))
    # return 'Check the console'
    ftime = get_time()
    forumobj = pydb.get(forum).val
    message = escape(data['message'])
    message = _format(message)
    if not message:
        return errorpage("You can't send a blank message!")
    if logged_in:
        author = escape(data['author'])
        unmodified_author = author
    else:
        author = escape(data['author'])
        if not author:
            return errorpage('Please enter a name')
        unmodified_author = author
        author = f'unverified$${author}'
    if forum in PROTECTED_CHANNELS and author not in DEVELOPERS + ('SimpleForum',):
        return errorpage('This is a developer-protected channel. Only SimpleForum and the devs can post here. Sorry.')
    forumobj.append({'author':author, 'message':message, 'time':ftime})
    pydb.set(forum, forumobj)
    session['author'] = data['author']
    # print(session['author'])
    pydb.save()
    del forumobj
    log(f'MESSAGING | New message on {forum} by {data["author"]}')
    try:
        forum_mailing_list = maildb.forums.get(forum).val
    except AttributeError:
        maildb.forums.create(forum, val=[])
        forum_mailing_list = maildb.forums.get(forum).val

    for user in forum_mailing_list:
        if user != author:
            for login in logindb.logins.val:
                if list(login.keys()) == [user]:
                    val = list(login.values())[0]
            recipient = val['email']
            send_thread_notif(recipient, user, forum, unmodified_author, data['message'])

    return redirect(f'/{forum}')

@app.route("/<forum>/len")
def len_forum(forum):
    try:
        return str(len(pydb.get(forum).val))
    except AttributeError:  # If forum doesn't exist
        return str(0)

@app.route('/<forum>/mail_toggle')
def mail_toggle(forum):
    logged_in = check_login_state()
    if logged_in == 'expired':
        return errorpage('Login has expired.')

    elif not logged_in:
        return errorpage('You are not logged in. (Your login may have expired)')

    try:
        forum_mailing_list = maildb.forums.get(forum).val
    except AttributeError:
        maildb.forums.create(forum, val=[])
        forum_mailing_list = maildb.forums.get(forum).val

    # log(f'DEBUG | {forum_mailing_list}')
    if session['username'] in forum_mailing_list:
        forum_mailing_list.remove(session['username'])
    else:
        forum_mailing_list.append(session['username'])

    if session['username'] in forum_mailing_list:
        eord = 'enabled'
    else:
        eord = 'disabled'

    maildb.forums.set(forum, forum_mailing_list)
    maildb.save()
    log(f'MAIL | {session["username"]} has {eord} email notifications for {forum}')

    return redirect(f'/{forum}')


@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('img/favicon.ico')

@app.route('/favicon.png')
def faviconpng():
    return app.send_static_file('img/favicon.png')

@app.route('/badge/<badge>')
def sendbadge(badge):
    if badge in ('verified.png', 'developer.png', 'early.png', 'exemplary.png'):
        return app.send_static_file(f'img/{badge}')
    else:
        return abort(404)

if __name__ == '__main__':
    app.secret_key = os.urandom(12)
    app.config["SESSION_PERMANENT"] = True
    app.run(host='127.0.0.1', port=5139)
