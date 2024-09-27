from flask import Flask, request, jsonify, render_template, redirect, url_for, json, session
from google.cloud import firestore
import os, requests
import firebase_admin
from firebase_admin import credentials, auth, firestore
from dotenv import load_dotenv
import pyrebase

load_dotenv()
app = Flask(__name__)

DIFY_API_URL=os.getenv('DIFY_API_URL')
MOTIVATION_GENERATE_API_KEY=os.getenv('MOTIVATION_GENERATE_API_KEY')
STRENGTH_GENERATE_API_KEY=os.getenv('STRENGTH_GENERATE_API_KEY')
TARGET_GENERATE_API_KEY=os.getenv('TARGET_GENERATE_API_KEY')
COMPETITOR_GENERATE_API_KEY=os.getenv('COMPETITOR_GENERATE_API_KEY')
app.secret_key =os.getenv('SECRET_KEY')
FIREBASE_API_KEY=os.getenv('FIREBASE_API_KEY')

# Firebase Admin SDK の初期化（サービスアカウントの JSON ファイルを使用）
# deploy時はコメントアウトして、下のコードを使う
# firebase_admin.initialize_app()
cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred)

# Firestoreに接続
def get_firestore_client():
    if os.getenv('FLASK_ENV') == 'production':
        return firestore.Client()  # GCP環境ではデフォルト認証情報を使用
    else:
        return firestore.Client()

db = firestore.Client.from_service_account_json(cred_path)

# Firebase Admin SDK の初期化を一度だけ行う
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        'databaseURL': "https://bizdraft.firebaseio.com"
    })

config = {
    'apiKey': "AIzaSyCu0_syEmpt5sTKVJkPDu79PUug3KRSXuk",
    'authDomain': "bizdraft.firebaseapp.com",
    'databaseURL': "https://bizdraft.firebaseio.com",
    'projectId': "bizdraft",
    'storageBucket': "bizdraft.appspot.com",
    'messagingSenderId': "369860809728",
    'appId': "1:369860809728:web:5fb1472449e4ce9f1574e5",
    'measurementId': "G-9E1F2B7N8T"
}

firebase = pyrebase.initialize_app(config)
auth_client = firebase.auth()

def run_dify_workflow(api_key, workflow_inputs):
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    payload = {
        'inputs': workflow_inputs,
        'response_mode': 'blocking',
        'user': 'user_id'
    }
    response = requests.post(DIFY_API_URL, headers=headers, json=payload)
    # APIの戻り値を取得
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": "Failed to fetch data from Dify API"}, response.status_code

# 認証チェックだけしている
@app.route('/')
def index():
    if 'user' in session:
        try:
            # Firebase Admin SDKでトークンの確認
            user = auth.verify_id_token(session['user']['idToken'])
            return redirect(url_for('dashboard'))
        except:
            return redirect(url_for('login'))
    return redirect(url_for('login'))

# サインインページ
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            # Firebase Authenticationでのログイン
            user = auth_client.sign_in_with_email_and_password(email, password)
            # セッションにユーザー情報を保存
            session['user'] = {
                'idToken': user['idToken'],
                'email': email,
                'localId': user['localId']  # FirebaseのUID
            }
            return redirect(url_for('dashboard'))
        except Exception as e:
            print(f"Signup error: {e}")
            return f"Invalid credentials, try again. Error: {e}"

    return render_template('login.html')

# サインアップページ
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            # Firebase Authenticationでの新規登録
            user = auth_client.create_user_with_email_and_password(email, password)
            return redirect(url_for('login'))
        except Exception as e:
            print(f"Signup error: {e}")
            return "Sign up failed, try again."

    return render_template('signup.html')

# ログアウト機能
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    user_id = session['user']['localId']
    doc_ref = db.collection(user_id).document('sougyou')
    doc = doc_ref.get()
    if doc.exists:
        data = doc.to_dict()
        status_setup = data.get('status_setup', 0)
        status_yourself = data.get('status_yourself', 0)
        status_business = data.get('status_business', 0)
        status_funds = data.get('status_funds', 0)
        status_partner = data.get('status_partner', 0)
        status_others = data.get('status_others', 0)
    else:
        status_setup = 0
        status_yourself = 0
        status_business = 0
        status_funds = 0
        status_partner = 0
        status_others = 0
    return render_template('dashboard.html', 
        status_setup=status_setup, 
        status_yourself=status_yourself, 
        status_business=status_business, 
        status_funds=status_funds, 
        status_partner=status_partner, 
        status_others=status_others)

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    record_ref = db.collection(session['user']['localId']).document('sougyou').collection('setup').document('data')
    doc = record_ref.get()
    data = doc.to_dict() if doc.exists else {}
    print(data)
    return render_template('setup.html', data=data)

@app.route('/setup_save', methods=['GET', 'POST'])
def setup_save():
    doc_ref = db.collection(session['user']['localId']).document('sougyou')
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'save_temp':
            # 一時保存の処理
            doc_ref.set({'status_setup':1}, merge=True)
        elif action == 'save_complete':
            # 保存完了の処理
            doc_ref.set({'status_setup':2}, merge=True)
    savedata = request.form.to_dict()
    records_ref=db.collection(session['user']['localId']).document('sougyou').collection('setup').document('data')
    records_ref.set(savedata, merge=True)
    print(savedata)
    return redirect(url_for('dashboard'))

@app.route('/yourself', methods=['GET', 'POST'])
def yourself():
    record_ref = db.collection(session['user']['localId']).document('sougyou').collection('yourself').document('data')
    doc = record_ref.get()
    data = doc.to_dict() if doc.exists else {}
    print(data)
    return render_template('yourself.html', data=data)

@app.route('/yourself_save', methods=['GET', 'POST'])
def yourself_save():
    doc_ref = db.collection(session['user']['localId']).document('sougyou')
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'save_temp':
            # 一時保存の処理
            doc_ref.set({'status_yourself':1}, merge=True)
        elif action == 'save_complete':
            # 保存完了の処理
            doc_ref.set({'status_yourself':2}, merge=True)
    savedata = request.form.to_dict()
    records_ref=db.collection(session['user']['localId']).document('sougyou').collection('yourself').document('data')
    records_ref.set(savedata, merge=True)
    print(savedata)
    return redirect(url_for('dashboard'))

@app.route('/business', methods=['GET', 'POST'])
def business():
    record_ref = db.collection(session['user']['localId']).document('sougyou').collection('business').document('data')
    doc = record_ref.get()
    data = doc.to_dict() if doc.exists else {}
    print(data)
    return render_template('business.html', data=data)

@app.route('/business_save', methods=['GET', 'POST'])
def business_save():
    doc_ref = db.collection(session['user']['localId']).document('sougyou')
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'save_temp':
            # 一時保存の処理
            doc_ref.set({'status_business':1}, merge=True)
        elif action == 'save_complete':
            # 保存完了の処理
            doc_ref.set({'status_business':2}, merge=True)
    savedata = request.form.to_dict()
    records_ref=db.collection(session['user']['localId']).document('sougyou').collection('business').document('data')
    records_ref.set(savedata, merge=True)
    print(savedata)
    return redirect(url_for('dashboard'))

@app.route('/funds', methods=['GET', 'POST'])
def funds():
    record_ref = db.collection(session['user']['localId']).document('sougyou').collection('funds').document('data')
    doc = record_ref.get()
    data = doc.to_dict() if doc.exists else {}
    print(data)
    return render_template('funds.html', data=data)

@app.route('/funds_save', methods=['GET', 'POST'])
def funds_save():
    doc_ref = db.collection(session['user']['localId']).document('sougyou')
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'save_temp':
            # 一時保存の処理
            doc_ref.set({'status_funds':1}, merge=True)
        elif action == 'save_complete':
            # 保存完了の処理
            doc_ref.set({'status_funds':2}, merge=True)
    savedata = request.form.to_dict()
    records_ref=db.collection(session['user']['localId']).document('sougyou').collection('funds').document('data')
    records_ref.set(savedata, merge=True)
    print(savedata)
    return redirect(url_for('dashboard'))

@app.route('/partner', methods=['GET', 'POST'])
def partner():
    record_ref = db.collection(session['user']['localId']).document('sougyou').collection('partner').document('data')
    doc = record_ref.get()
    data = doc.to_dict() if doc.exists else {}
    print(data)
    return render_template('partner.html', data=data)

@app.route('/partner_save', methods=['GET', 'POST'])
def partner_save():
    doc_ref = db.collection(session['user']['localId']).document('sougyou')
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'save_temp':
            # 一時保存の処理
            doc_ref.set({'status_partner':1}, merge=True)
        elif action == 'save_complete':
            # 保存完了の処理
            doc_ref.set({'status_partner':2}, merge=True)
    savedata = request.form.to_dict()
    records_ref=db.collection(session['user']['localId']).document('sougyou').collection('partner').document('data')
    records_ref.set(savedata, merge=True)
    print(savedata)
    return redirect(url_for('dashboard'))

@app.route('/others', methods=['GET', 'POST'])
def others():
    record_ref = db.collection(session['user']['localId']).document('sougyou').collection('others').document('data')
    doc = record_ref.get()
    data = doc.to_dict() if doc.exists else {}
    print(data)
    return render_template('others.html', data=data)

@app.route('/others_save', methods=['GET', 'POST'])
def others_save():
    doc_ref = db.collection(session['user']['localId']).document('sougyou')
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'save_temp':
            # 一時保存の処理
            doc_ref.set({'status_others':1}, merge=True)
        elif action == 'save_complete':
            # 保存完了の処理
            doc_ref.set({'status_others':2}, merge=True)
    savedata = request.form.to_dict()
    records_ref=db.collection(session['user']['localId']).document('sougyou').collection('others').document('data')
    records_ref.set(savedata, merge=True)
    print(savedata)
    return redirect(url_for('dashboard'))

@app.route('/motivation_generate', methods=['POST'])
def motivation_generate():
    data = request.get_json()
    input_sentence = data.get('motivation_sentence')
    workflow_inputs = {
        'motivation_sentence': input_sentence
    }
    result = run_dify_workflow(MOTIVATION_GENERATE_API_KEY, workflow_inputs)
    return jsonify({'ai_generated_text': result['data']['outputs']['text']})

@app.route('/strength_generate', methods=['POST'])
def strength_generate():
    data = request.get_json()
    input_sentence = data.get('strength_sentence')
    workflow_inputs = {
        'strength_sentence': input_sentence
    }
    result = run_dify_workflow(STRENGTH_GENERATE_API_KEY, workflow_inputs)
    return jsonify({'ai_generated_text': result['data']['outputs']['text']})

@app.route('/target_generate', methods=['POST'])
def target_generate():
    data = request.get_json()
    input_sentence = data.get('target_sentence')
    workflow_inputs = {
        'target_sentence': input_sentence
    }
    result = run_dify_workflow(TARGET_GENERATE_API_KEY, workflow_inputs)
    return jsonify({'ai_generated_text': result['data']['outputs']['text']})

@app.route('/competitor_generate', methods=['POST'])
def competitor_generate():
    data = request.get_json()
    input_sentence = data.get('competitor_sentence')
    workflow_inputs = {
        'competitor_sentence': input_sentence
    }
    result = run_dify_workflow(COMPETITOR_GENERATE_API_KEY, workflow_inputs)
    return jsonify({'ai_generated_text': result['data']['outputs']['text']})

# アプリケーションのエントリーポイント
if __name__ == '__main__':
    app.run(debug=True)