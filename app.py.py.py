# -*- coding: utf-8 -*-
"""
Chatbot - Equipe Nationale Marocaine de Football
=================================================
Application Flask "tout-en-un" (un seul fichier, comme demande) :
 - inscription / connexion (mots de passe haches, jamais en clair)
 - protection des pages du chatbot pour les utilisateurs non connectes
 - chatbot base sur des regles (regex) qui repond aux questions sur
   les joueurs, l'histoire, les competitions, etc.
 - interface HTML/CSS/JS moderne, responsive, aux couleurs du Maroc
   (rouge / vert / blanc / touches dorees)

Pour un etudiant debutant : tout le code est commente en francais.
Voir la fin du fichier pour les instructions d'installation et de lancement.

DEPENDANCES (pas de requirements.txt separe : tout est dans ce fichier)
-------------------------------------------------------------------------
Ce projet a besoin de deux paquets Python :
    Flask>=3.0.0
    Werkzeug>=3.0.0

Pour les installer, deux options :
  1) Directement :
        pip install Flask Werkzeug
  2) En recreant un fichier requirements.txt vous-meme avec les deux lignes
     ci-dessus, puis :
        pip install -r requirements.txt
"""

import os
import re
import random
import sqlite3
from functools import wraps
from datetime import timedelta, datetime

from flask import (
    Flask, request, session, redirect, url_for,
    render_template_string, jsonify, g
)
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------------------------------------------------------------------
# 1) CONFIGURATION DE BASE
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "chatbot.db")

app = Flask(__name__)

# IMPORTANT (securite) : en production, ne mettez jamais une cle "en dur"
# dans le code. Utilisez plutot une variable d'environnement, par exemple :
#   app.secret_key = os.environ.get("SECRET_KEY")
# Ici on met une valeur par defaut UNIQUEMENT pour que le projet fonctionne
# tout de suite en local / en cours.
app.secret_key = os.environ.get("SECRET_KEY", "cle-secrete-a-changer-en-production")

# Duree de la session si l'utilisateur coche "Se souvenir de moi"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)


# ---------------------------------------------------------------------------
# 2) BASE DE DONNEES (SQLite)
# ---------------------------------------------------------------------------

def get_db():
    """Ouvre (ou reutilise) une connexion SQLite pour la requete en cours."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Cree la table des utilisateurs si elle n'existe pas encore."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# 3) OUTILS DE VALIDATION (cote serveur - a NE JAMAIS retirer,
#    meme si on valide deja cote client en JavaScript)
# ---------------------------------------------------------------------------

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email):
    return bool(EMAIL_REGEX.match(email or ""))


def is_valid_password(password):
    return bool(password) and len(password) >= 8


def login_required(view_func):
    """Decorateur : bloque l'acces a une page si l'utilisateur n'est pas connecte."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# 4) LE "CERVEAU" DU CHATBOT
#    Base de regles simples (regex -> reponses) sur l'equipe nationale.
#    NB : ces informations sont donnees a titre pedagogique / general.
#    Pensez a les mettre a jour regulierement (nom du selectionneur,
#    resultats recents, calendrier...) car elles peuvent changer.
# ---------------------------------------------------------------------------

FOOTBALL_KB = [
    (r"\b(bonjour|salut|slt|hello|bonsoir|coucou)\b", [
        "Bonjour ! ⚽ Je suis le chatbot des Lions de l'Atlas. "
        "Posez-moi une question sur les joueurs, l'histoire, les competitions "
        "ou le staff de l'equipe nationale marocaine !",
    ]),
    (r"\bmerci\b", [
        "De rien, avec plaisir ! Allez les Lions ! 🦁",
        "Je vous en prie !",
    ]),
    (r"\b(au revoir|a bientot|a\+|bye)\b", [
        "A bientot, et allez le Maroc ! 🇲🇦",
    ]),
    (r"(entraineur|coach|selectionneur)", [
        "Le staff technique de l'equipe nationale est dirige par un selectionneur "
        "nomme par la Federation Royale Marocaine de Football (FRMF). "
        "Pour le nom exact et a jour, consultez le site officiel frmf.ma.",
    ]),
    (r"(gardien|bounou)", [
        "Le Maroc a longtemps pu compter sur un gardien de tres haut niveau, "
        "notamment lors du parcours historique de la Coupe du Monde 2022. "
        "La composition actuelle des gardiens evolue selon les convocations.",
    ]),
    (r"(capitaine)", [
        "Le brassard de capitaine est traditionnellement confie a un joueur "
        "experimente du groupe. Consultez frmf.ma pour la liste et le capitaine "
        "actuels, qui peuvent changer selon les matchs.",
    ]),
    (r"(hakimi|ziyech|boufal|en\s*nesyri|ounahi|mazraoui)", [
        "Le Maroc dispose de nombreux joueurs evoluant dans les plus grands "
        "championnats europeens. La liste des joueurs convoques change a "
        "chaque rassemblement : je vous invite a verifier la derniere liste "
        "officielle sur frmf.ma.",
    ]),
    (r"(coupe du monde|mondial|2022|qatar)", [
        "Le Maroc a marque l'histoire en 2022 en devenant la premiere equipe "
        "africaine et arabe a atteindre les demi-finales d'une Coupe du Monde, "
        "lors de l'edition organisee au Qatar. Une performance historique pour "
        "le football africain et arabe !",
    ]),
    (r"(can\b|coupe d.?afrique)", [
        "La Coupe d'Afrique des Nations (CAN) est l'une des principales "
        "competitions ou le Maroc s'illustre regulierement. Le Maroc a deja "
        "remporte la CAN en 1976 et a organise l'edition 2025.",
    ]),
    (r"(histoire|fond[ée]e?|creation|1956)", [
        "La Federation Royale Marocaine de Football (FRMF) a ete fondee en "
        "1955-1956, peu apres l'independance du Maroc. L'equipe nationale "
        "porte depuis les couleurs du pays sur la scene internationale.",
    ]),
    (r"(surnom|lions de l.?atlas)", [
        "L'equipe nationale marocaine est surnommee les 'Lions de l'Atlas', "
        "en reference a la chaine de montagnes de l'Atlas et a la force du lion, "
        "symbole present sur le blason de la federation.",
    ]),
    (r"(prochain match|calendrier|programme)", [
        "Je n'ai pas acces au calendrier en direct pour le moment. "
        "Consultez le site officiel de la FRMF (frmf.ma) pour les prochaines "
        "dates de matchs des Lions de l'Atlas.",
    ]),
    (r"(resultat|score)", [
        "Je n'ai pas les resultats en direct, mais je peux vous parler avec "
        "plaisir de l'histoire, des competitions ou des joueurs emblematiques "
        "de l'equipe nationale !",
    ]),
    (r"(stade)", [
        "Le Maroc dispose de plusieurs grands stades, comme le Complexe "
        "Sportif Mohammed V a Casablanca, et prepare de nouvelles infrastructures "
        "dans le cadre de futures grandes competitions.",
    ]),
    (r"(qualification|eliminatoire)", [
        "Les qualifications de l'equipe nationale se jouent selon le calendrier "
        "de la CAF et de la FIFA. Pour le classement du groupe et les prochaines "
        "rencontres, le site frmf.ma est la reference la plus a jour.",
    ]),
    (r"(couleur|maillot)", [
        "Le maillot domicile de l'equipe nationale est traditionnellement rouge "
        "avec des touches de vert, les couleurs du drapeau marocain.",
    ]),
]

FALLBACK_RESPONSES = [
    "Interessant ! Je peux vous renseigner sur les joueurs, l'histoire, "
    "les competitions (CAN, Coupe du Monde) ou le staff des Lions de l'Atlas. "
    "Que voulez-vous savoir ?",
    "Je ne suis pas sur de bien comprendre. Essayez par exemple : "
    "\"Parle-moi de la Coupe du Monde 2022\" ou \"Quel est le surnom de l'equipe ?\"",
]


def get_bot_response(message):
    text = (message or "").strip().lower()
    if not text:
        return "Posez-moi une question sur l'equipe nationale marocaine ! ⚽"
    for pattern, responses in FOOTBALL_KB:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return random.choice(responses)
    return random.choice(FALLBACK_RESPONSES)


# ---------------------------------------------------------------------------
# 5) CSS PARTAGE (couleurs du Maroc : rouge / vert / blanc / dore)
# ---------------------------------------------------------------------------

BASE_CSS = """
:root{
  --rouge:#c1272d;
  --rouge-fonce:#8f1c21;
  --vert:#046a38;
  --vert-fonce:#03502a;
  --or:#d4af37;
  --blanc:#ffffff;
  --gris-clair:#f4f1ea;
  --gris-texte:#3a3a3a;
  --radius:14px;
  --ombre:0 10px 30px rgba(0,0,0,.12);
}
*{box-sizing:border-box;}
body{
  margin:0;
  font-family:'Segoe UI',Roboto,Arial,sans-serif;
  background:linear-gradient(160deg,var(--vert) 0%,var(--vert-fonce) 45%,var(--rouge-fonce) 100%);
  min-height:100vh;
  color:var(--gris-texte);
  display:flex;
  align-items:center;
  justify-content:center;
  padding:20px;
}
.card{
  background:var(--blanc);
  border-radius:var(--radius);
  box-shadow:var(--ombre);
  width:100%;
  max-width:420px;
  padding:34px 30px;
  border-top:6px solid var(--or);
}
.brand{
  text-align:center;
  margin-bottom:18px;
}
.brand .ball{font-size:42px;display:block;margin-bottom:6px;}
.brand h1{
  font-size:20px;
  margin:0;
  color:var(--rouge);
  letter-spacing:.3px;
}
.brand p{margin:4px 0 0;font-size:13px;color:#777;}
label{
  display:block;
  font-size:13px;
  font-weight:600;
  margin:14px 0 6px;
  color:var(--gris-texte);
}
input[type=text],input[type=email],input[type=password]{
  width:100%;
  padding:11px 13px;
  border:1.5px solid #ddd;
  border-radius:10px;
  font-size:14px;
  transition:border-color .15s;
}
input:focus{outline:none;border-color:var(--vert);}
input.invalid{border-color:var(--rouge);}
.error-msg{
  color:var(--rouge);
  font-size:12.5px;
  margin-top:4px;
  min-height:14px;
}
.row{display:flex;align-items:center;justify-content:space-between;margin:14px 0 4px;font-size:13px;}
.checkbox-row{display:flex;align-items:center;gap:8px;}
.btn{
  width:100%;
  padding:12px;
  margin-top:20px;
  border:none;
  border-radius:10px;
  background:linear-gradient(135deg,var(--rouge),var(--rouge-fonce));
  color:var(--blanc);
  font-size:15px;
  font-weight:700;
  cursor:pointer;
  transition:transform .1s, box-shadow .15s;
}
.btn:hover{transform:translateY(-1px);box-shadow:0 8px 18px rgba(193,39,45,.35);}
.btn.secondary{background:linear-gradient(135deg,var(--vert),var(--vert-fonce));}
.links{text-align:center;margin-top:16px;font-size:13px;}
.links a{color:var(--vert);text-decoration:none;font-weight:600;}
.links a:hover{text-decoration:underline;}
.flash{
  background:#fdecea;
  border:1px solid var(--rouge);
  color:var(--rouge-fonce);
  padding:10px 12px;
  border-radius:8px;
  font-size:13px;
  margin-bottom:14px;
}
.flash.success{background:#e9f7ef;border-color:var(--vert);color:var(--vert-fonce);}

/* ---------- Interface du chat ---------- */
.chat-wrap{
  width:100%;
  max-width:640px;
  background:var(--blanc);
  border-radius:var(--radius);
  box-shadow:var(--ombre);
  overflow:hidden;
  display:flex;
  flex-direction:column;
  height:85vh;
  max-height:720px;
  border-top:6px solid var(--or);
}
.chat-header{
  background:linear-gradient(120deg,var(--rouge),var(--vert-fonce));
  color:var(--blanc);
  padding:16px 20px;
  display:flex;
  align-items:center;
  justify-content:space-between;
}
.chat-header .title{display:flex;align-items:center;gap:10px;}
.chat-header .title .ball{font-size:26px;}
.chat-header h2{margin:0;font-size:16px;}
.chat-header .sub{font-size:11.5px;opacity:.85;margin-top:2px;}
.header-actions{display:flex;gap:8px;}
.icon-btn{
  background:rgba(255,255,255,.15);
  border:1px solid rgba(255,255,255,.4);
  color:var(--blanc);
  border-radius:8px;
  padding:6px 10px;
  font-size:12px;
  cursor:pointer;
}
.icon-btn:hover{background:rgba(255,255,255,.28);}
.messages{
  flex:1;
  overflow-y:auto;
  padding:18px;
  background:var(--gris-clair);
  display:flex;
  flex-direction:column;
  gap:10px;
}
.msg{
  max-width:78%;
  padding:10px 13px;
  border-radius:14px;
  font-size:14px;
  line-height:1.4;
  position:relative;
  box-shadow:0 2px 6px rgba(0,0,0,.06);
}
.msg .time{display:block;font-size:10px;opacity:.6;margin-top:4px;}
.msg.user{
  align-self:flex-end;
  background:linear-gradient(135deg,var(--vert),var(--vert-fonce));
  color:var(--blanc);
  border-bottom-right-radius:4px;
}
.msg.bot{
  align-self:flex-start;
  background:var(--blanc);
  border:1.5px solid #eee;
  border-left:4px solid var(--rouge);
  border-bottom-left-radius:4px;
}
.typing{
  align-self:flex-start;
  font-size:12.5px;
  color:#888;
  padding:4px 6px;
  font-style:italic;
}
.chat-input{
  display:flex;
  gap:10px;
  padding:14px;
  border-top:1px solid #eee;
  background:var(--blanc);
}
.chat-input input{
  flex:1;
  padding:12px 14px;
  border-radius:24px;
  border:1.5px solid #ddd;
  font-size:14px;
}
.chat-input input:focus{outline:none;border-color:var(--vert);}
.send-btn{
  border:none;
  background:linear-gradient(135deg,var(--rouge),var(--rouge-fonce));
  color:var(--blanc);
  width:46px;height:46px;
  border-radius:50%;
  font-size:18px;
  cursor:pointer;
  display:flex;align-items:center;justify-content:center;
}
.send-btn:hover{transform:scale(1.05);}

@media (max-width:480px){
  .chat-wrap{height:92vh;border-radius:8px;}
  .card{padding:26px 20px;}
}
"""


# ---------------------------------------------------------------------------
# 6) TEMPLATES HTML (Jinja) - un seul fichier, tout est ici
# ---------------------------------------------------------------------------

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Connexion - Chatbot Lions de l'Atlas</title>
<style>{{ css }}</style>
</head>
<body>
<div class="card">
  <div class="brand">
    <span class="ball">⚽</span>
    <h1>Chatbot Lions de l'Atlas</h1>
    <p>Connectez-vous pour discuter avec le chatbot</p>
  </div>

  {% if error %}<div class="flash">{{ error }}</div>{% endif %}
  {% if success %}<div class="flash success">{{ success }}</div>{% endif %}

  <form id="loginForm" method="POST" novalidate>
    <label for="email">Adresse e-mail</label>
    <input type="email" id="email" name="email" placeholder="vous@exemple.com" required>
    <div class="error-msg" id="emailError"></div>

    <label for="password">Mot de passe</label>
    <input type="password" id="password" name="password" placeholder="********" required>
    <div class="error-msg" id="passwordError"></div>

    <div class="row">
      <div class="checkbox-row">
        <input type="checkbox" id="remember" name="remember" style="width:auto;">
        <label for="remember" style="margin:0;font-weight:400;">Se souvenir de moi</label>
      </div>
      <a href="{{ url_for('forgot_password') }}" style="color:var(--vert);font-size:12.5px;">Mot de passe oublie ?</a>
    </div>

    <button type="submit" class="btn">Se connecter</button>
  </form>

  <div class="links">
    Pas encore de compte ? <a href="{{ url_for('register') }}">Creer un compte</a>
  </div>
</div>

<script>
const form = document.getElementById('loginForm');
form.addEventListener('submit', function(e){
  let valid = true;
  const email = document.getElementById('email');
  const password = document.getElementById('password');
  const emailError = document.getElementById('emailError');
  const passwordError = document.getElementById('passwordError');

  emailError.textContent = ''; passwordError.textContent = '';
  email.classList.remove('invalid'); password.classList.remove('invalid');

  const emailRegex = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
  if(!emailRegex.test(email.value.trim())){
    emailError.textContent = "Veuillez saisir une adresse e-mail valide.";
    email.classList.add('invalid');
    valid = false;
  }
  if(password.value.length < 8){
    passwordError.textContent = "Le mot de passe doit contenir au moins 8 caracteres.";
    password.classList.add('invalid');
    valid = false;
  }
  if(!valid) e.preventDefault();
});
</script>
</body>
</html>
"""

REGISTER_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Inscription - Chatbot Lions de l'Atlas</title>
<style>{{ css }}</style>
</head>
<body>
<div class="card">
  <div class="brand">
    <span class="ball">🏟️</span>
    <h1>Creer un compte</h1>
    <p>Rejoignez le chatbot des Lions de l'Atlas</p>
  </div>

  {% if error %}<div class="flash">{{ error }}</div>{% endif %}

  <form id="registerForm" method="POST" novalidate>
    <label for="full_name">Nom complet</label>
    <input type="text" id="full_name" name="full_name" placeholder="Votre nom complet" required>
    <div class="error-msg" id="nameError"></div>

    <label for="email">Adresse e-mail</label>
    <input type="email" id="email" name="email" placeholder="vous@exemple.com" required>
    <div class="error-msg" id="emailError"></div>

    <label for="password">Mot de passe</label>
    <input type="password" id="password" name="password" placeholder="8 caracteres minimum" required>
    <div class="error-msg" id="passwordError"></div>

    <label for="confirm_password">Confirmer le mot de passe</label>
    <input type="password" id="confirm_password" name="confirm_password" placeholder="********" required>
    <div class="error-msg" id="confirmError"></div>

    <button type="submit" class="btn secondary">S'inscrire</button>
  </form>

  <div class="links">
    Deja un compte ? <a href="{{ url_for('login') }}">Se connecter</a>
  </div>
</div>

<script>
const form = document.getElementById('registerForm');
form.addEventListener('submit', function(e){
  let valid = true;
  const name = document.getElementById('full_name');
  const email = document.getElementById('email');
  const password = document.getElementById('password');
  const confirm = document.getElementById('confirm_password');

  document.getElementById('nameError').textContent = '';
  document.getElementById('emailError').textContent = '';
  document.getElementById('passwordError').textContent = '';
  document.getElementById('confirmError').textContent = '';
  [name,email,password,confirm].forEach(i => i.classList.remove('invalid'));

  if(name.value.trim().length < 2){
    document.getElementById('nameError').textContent = "Veuillez saisir votre nom complet.";
    name.classList.add('invalid'); valid = false;
  }
  const emailRegex = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
  if(!emailRegex.test(email.value.trim())){
    document.getElementById('emailError').textContent = "Adresse e-mail invalide.";
    email.classList.add('invalid'); valid = false;
  }
  if(password.value.length < 8){
    document.getElementById('passwordError').textContent = "8 caracteres minimum requis.";
    password.classList.add('invalid'); valid = false;
  }
  if(confirm.value !== password.value || confirm.value === ""){
    document.getElementById('confirmError').textContent = "Les mots de passe ne correspondent pas.";
    confirm.classList.add('invalid'); valid = false;
  }
  if(!valid) e.preventDefault();
});
</script>
</body>
</html>
"""

FORGOT_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mot de passe oublie</title>
<style>{{ css }}</style>
</head>
<body>
<div class="card">
  <div class="brand">
    <span class="ball">⚽</span>
    <h1>Mot de passe oublie</h1>
    <p>Entrez votre e-mail pour recevoir un lien de reinitialisation</p>
  </div>
  {% if success %}<div class="flash success">{{ success }}</div>{% endif %}
  <form method="POST" novalidate>
    <label for="email">Adresse e-mail</label>
    <input type="email" id="email" name="email" required>
    <button type="submit" class="btn">Envoyer le lien</button>
  </form>
  <div class="links"><a href="{{ url_for('login') }}">Retour a la connexion</a></div>
</div>
</body>
</html>
"""

CHAT_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chatbot Lions de l'Atlas</title>
<style>{{ css }}</style>
</head>
<body>
<div class="chat-wrap">
  <div class="chat-header">
    <div class="title">
      <span class="ball">⚽</span>
      <div>
        <h2>Lions de l'Atlas - Chatbot</h2>
        <div class="sub">Bonjour {{ full_name }} !</div>
      </div>
    </div>
    <div class="header-actions">
      <button class="icon-btn" id="clearBtn" title="Recommencer la conversation">Effacer</button>
      <a class="icon-btn" href="{{ url_for('logout') }}" style="text-decoration:none;">Deconnexion</a>
    </div>
  </div>

  <div class="messages" id="messages"></div>

  <form class="chat-input" id="chatForm" autocomplete="off">
    <input type="text" id="messageInput" placeholder="Posez une question sur l'equipe nationale..." required>
    <button type="submit" class="send-btn" title="Envoyer">➤</button>
  </form>
</div>

<script>
const messagesEl = document.getElementById('messages');
const form = document.getElementById('chatForm');
const input = document.getElementById('messageInput');
const clearBtn = document.getElementById('clearBtn');

function nowStr(){
  const d = new Date();
  return d.getHours().toString().padStart(2,'0') + ':' + d.getMinutes().toString().padStart(2,'0');
}

function addMessage(text, sender){
  const div = document.createElement('div');
  div.className = 'msg ' + sender;
  div.innerHTML = escapeHtml(text) + '<span class="time">' + nowStr() + '</span>';
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function escapeHtml(str){
  const d = document.createElement('div');
  d.innerText = str;
  return d.innerHTML;
}

function showTyping(){
  const div = document.createElement('div');
  div.className = 'typing';
  div.id = 'typingIndicator';
  div.textContent = 'Le chatbot ecrit...';
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function hideTyping(){
  const el = document.getElementById('typingIndicator');
  if(el) el.remove();
}

function loadHistory(){
  const saved = JSON.parse(localStorage.getItem('chatHistory') || '[]');
  saved.forEach(m => addMessage(m.text, m.sender));
  if(saved.length === 0){
    addMessage("Salut ! Je suis le chatbot des Lions de l'Atlas ⚽. Posez-moi une question sur les joueurs, l'histoire ou les competitions !", 'bot');
  }
}

function saveMessage(text, sender){
  const saved = JSON.parse(localStorage.getItem('chatHistory') || '[]');
  saved.push({text, sender});
  localStorage.setItem('chatHistory', JSON.stringify(saved));
}

form.addEventListener('submit', async function(e){
  e.preventDefault();
  const text = input.value.trim();
  if(!text) return;
  addMessage(text, 'user');
  saveMessage(text, 'user');
  input.value = '';
  showTyping();

  try{
    const res = await fetch("{{ url_for('api_chat') }}", {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({message: text})
    });
    const data = await res.json();
    hideTyping();
    setTimeout(() => {
      addMessage(data.response, 'bot');
      saveMessage(data.response, 'bot');
    }, 250);
  }catch(err){
    hideTyping();
    addMessage("Erreur de connexion au serveur.", 'bot');
  }
});

clearBtn.addEventListener('click', function(){
  if(confirm('Recommencer la conversation ?')){
    localStorage.removeItem('chatHistory');
    messagesEl.innerHTML = '';
    addMessage("Conversation reinitialisee. Posez-moi une question sur l'equipe nationale !", 'bot');
  }
});

loadHistory();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# 7) ROUTES
# ---------------------------------------------------------------------------

@app.route("/")
@login_required
def home():
    return render_template_string(
        CHAT_TEMPLATE, css=BASE_CSS, full_name=session.get("full_name", "")
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # --- Validation cote serveur (obligatoire, meme si deja fait en JS) ---
        if len(full_name) < 2:
            return render_template_string(REGISTER_TEMPLATE, css=BASE_CSS,
                                           error="Veuillez saisir votre nom complet.")
        if not is_valid_email(email):
            return render_template_string(REGISTER_TEMPLATE, css=BASE_CSS,
                                           error="Adresse e-mail invalide.")
        if not is_valid_password(password):
            return render_template_string(REGISTER_TEMPLATE, css=BASE_CSS,
                                           error="Le mot de passe doit contenir au moins 8 caracteres.")
        if password != confirm_password:
            return render_template_string(REGISTER_TEMPLATE, css=BASE_CSS,
                                           error="Les mots de passe ne correspondent pas.")

        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            return render_template_string(REGISTER_TEMPLATE, css=BASE_CSS,
                                           error="Un compte existe deja avec cet e-mail.")

        # Le mot de passe n'est JAMAIS stocke en clair : on le hache.
        password_hash = generate_password_hash(password)
        db.execute(
            "INSERT INTO users (full_name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (full_name, email, password_hash, datetime.utcnow().isoformat())
        )
        db.commit()

        return redirect(url_for("login", registered=1))

    return render_template_string(REGISTER_TEMPLATE, css=BASE_CSS, error=None)


@app.route("/login", methods=["GET", "POST"])
def login():
    success = None
    if request.args.get("registered"):
        success = "Compte cree avec succes ! Vous pouvez maintenant vous connecter."

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            return render_template_string(LOGIN_TEMPLATE, css=BASE_CSS,
                                           error="E-mail ou mot de passe incorrect.", success=None)

        session.clear()
        session["user_id"] = user["id"]
        session["full_name"] = user["full_name"]
        session.permanent = bool(remember)

        return redirect(url_for("home"))

    return render_template_string(LOGIN_TEMPLATE, css=BASE_CSS, error=None, success=success)


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    success = None
    if request.method == "POST":
        # NOTE pedagogique : l'envoi reel d'un e-mail necessite un service
        # externe (SendGrid, SMTP...) et une cle API qui ne doit JAMAIS
        # etre placee dans le code Front-End. Ici on simule la reponse.
        success = "Si un compte existe avec cet e-mail, un lien de reinitialisation a ete envoye."
    return render_template_string(FORGOT_TEMPLATE, css=BASE_CSS, success=success)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    response = get_bot_response(message)
    return jsonify({
        "response": response,
        "time": datetime.utcnow().strftime("%H:%M")
    })


# ---------------------------------------------------------------------------
# 8) LANCEMENT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    app.run(debug=True)


# ===========================================================================
# INSTRUCTIONS D'INSTALLATION ET DE LANCEMENT (pour un etudiant debutant)
# ===========================================================================
#
# 1) Installer Python (3.9 ou plus recent) si ce n'est pas deja fait.
#
# 2) Dans le dossier du projet, creer un environnement virtuel (recommande) :
#       python -m venv venv
#       # Windows :
#       venv\\Scripts\\activate
#       # Mac / Linux :
#       source venv/bin/activate
#
# 3) Installer les dependances (voir requirements.txt) :
#       pip install -r requirements.txt
#
# 4) Lancer l'application :
#       python app.py
#
# 5) Ouvrir le navigateur a l'adresse :
#       http://127.0.0.1:5000
#
#    - La premiere fois, cliquez sur "Creer un compte" pour vous inscrire.
#    - Connectez-vous ensuite pour acceder au chatbot.
#    - Le fichier "chatbot.db" (base SQLite) est cree automatiquement au
#      premier lancement, dans le meme dossier que app.py.
#
# EXPLICATION SIMPLE (pour debutant) :
# -------------------------------------
# - Flask est un "micro-framework" web en Python : il permet de creer des
#   pages web et une API avec peu de code.
# - Chaque "route" (@app.route(...)) correspond a une page ou une action
#   (ex: /login = page de connexion, /api/chat = le point d'entree que le
#   JavaScript appelle pour obtenir la reponse du chatbot).
# - Les mots de passe ne sont JAMAIS stockes tels quels : la fonction
#   generate_password_hash() les transforme en une empreinte illisible,
#   et check_password_hash() verifie le mot de passe sans jamais le
#   "dechiffrer" (le hachage n'est pas reversible, c'est voulu).
# - "session" est un mecanisme fourni par Flask pour se souvenir qu'un
#   utilisateur est connecte, via un cookie securise signe par
#   app.secret_key.
# - Le decorateur @login_required est une fonction qui "enveloppe" une
#   route pour verifier, avant d'executer la page, que l'utilisateur est
#   bien connecte -- sinon on le renvoie vers /login.
# - Le chatbot lui-meme est tres simple : il compare le message de
#   l'utilisateur a une liste d'expressions regulieres (regex) et renvoie
#   une reponse associee. C'est une approche "a base de regles", plus
#   simple qu'une IA, mais parfaite pour un premier projet.
# ===========================================================================
