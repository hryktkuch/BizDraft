from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_file
from google.cloud import firestore
import os, requests
import firebase_admin
from firebase_admin import auth
from dotenv import load_dotenv
import pyrebase

from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape, A3
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from PyPDF2 import PdfWriter, PdfReader
import datetime

# 環境変数を読み込み
load_dotenv()
app = Flask(__name__)

# APIキーやシークレットキーを環境変数から取得
DIFY_API_URL = os.getenv('DIFY_API_URL')
MOTIVATION_GENERATE_API_KEY = os.getenv('MOTIVATION_GENERATE_API_KEY')
STRENGTH_GENERATE_API_KEY = os.getenv('STRENGTH_GENERATE_API_KEY')
TARGET_GENERATE_API_KEY = os.getenv('TARGET_GENERATE_API_KEY')
COMPETITOR_GENERATE_API_KEY = os.getenv('COMPETITOR_GENERATE_API_KEY')
app.secret_key = os.getenv('SECRET_KEY')
FIREBASE_API_KEY = os.getenv('FIREBASE_API_KEY')
REASONING_INITIAL_API_KEY = os.getenv('REASONING_INITIAL_API_KEY')
REASONING_STABLE_API_KEY = os.getenv('REASONING_STABLE_API_KEY')

# Firebase Admin SDK の初期化（App Engineでは認証情報の明示指定は不要）
if not firebase_admin._apps:
    firebase_admin.initialize_app()

# Firestoreに接続
def get_firestore_client():
    if os.getenv('GAE_ENV', '').startswith('standard'):  # App Engineの標準環境を確認
        return firestore.Client()  # App Engineではデフォルト認証情報を使用
    else:
        cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')  # ローカル用の認証ファイルパス
        return firestore.Client.from_service_account_json(cred_path)  # ローカル開発環境用

db = get_firestore_client()

# Firebase SDKの初期化
config = {
    'apiKey': FIREBASE_API_KEY,
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
    doc2_ref = db.collection(user_id).document('sougyou').collection('setup').document('data')
    doc2 = doc2_ref.get()
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
    if doc2.exists:
        data2 = doc2.to_dict()
        if data2.get('business_name') != '':
            business_name = data2.get('business_name', '') + 'の'
        else:
            business_name = ''
    else:
        business_name = ''
    return render_template('dashboard.html', 
        status_setup=status_setup, 
        status_yourself=status_yourself, 
        status_business=status_business, 
        status_funds=status_funds, 
        status_partner=status_partner, 
        status_others=status_others,
        business_name=business_name)

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
    if input_sentence == '':
        input_sentence = '（なし）'
    workflow_inputs = {
        'motivation_sentence': input_sentence
    }
    result = run_dify_workflow(MOTIVATION_GENERATE_API_KEY, workflow_inputs)
    return jsonify({'ai_generated_text': result['data']['outputs']['text']})

@app.route('/strength_generate', methods=['POST'])
def strength_generate():
    data = request.get_json()
    input_sentence = data.get('strength_sentence')
    if input_sentence == '':
        input_sentence = '（なし）'
    workflow_inputs = {
        'strength_sentence': input_sentence
    }
    result = run_dify_workflow(STRENGTH_GENERATE_API_KEY, workflow_inputs)
    return jsonify({'ai_generated_text': result['data']['outputs']['text']})

@app.route('/target_generate', methods=['POST'])
def target_generate():
    data = request.get_json()
    input_sentence = data.get('target_sentence')
    if input_sentence == '':
        input_sentence = '（なし）'
    workflow_inputs = {
        'target_sentence': input_sentence
    }
    result = run_dify_workflow(TARGET_GENERATE_API_KEY, workflow_inputs)
    return jsonify({'ai_generated_text': result['data']['outputs']['text']})

@app.route('/competitor_generate', methods=['POST'])
def competitor_generate():
    data = request.get_json()
    input_sentence = data.get('competitor_sentence')
    if input_sentence == '':
        input_sentence = '（なし）'
    workflow_inputs = {
        'competitor_sentence': input_sentence
    }
    result = run_dify_workflow(COMPETITOR_GENERATE_API_KEY, workflow_inputs)
    return jsonify({'ai_generated_text': result['data']['outputs']['text']})

@app.route('/reasoning_initial_generate', methods=['POST'])
def reasoning_initial_generate():
    data = request.get_json()
    input_sentence = data.get('reasoning_sentence_initial')
    if input_sentence == '':
        input_sentence = '（なし）'
    workflow_inputs = {
        'reasoning_sentence_initial': input_sentence
    }
    result = run_dify_workflow(REASONING_INITIAL_API_KEY, workflow_inputs)
    return jsonify({'ai_generated_text': result['data']['outputs']['text']})

@app.route('/reasoning_stable_generate', methods=['POST'])
def reasoning_stable_generate():
    data = request.get_json()
    input_sentence = data.get('reasoning_sentence_stable')
    if input_sentence == '':
        input_sentence = '（なし）'
    workflow_inputs = {
        'reasoning_sentence_stable': input_sentence
    }
    result = run_dify_workflow(REASONING_STABLE_API_KEY, workflow_inputs)
    return jsonify({'ai_generated_text': result['data']['outputs']['text']})

def add_paragraph(x_position, y_position, frame_width, frame_height, long_text, c):
    # スタイルを取得
    styles = getSampleStyleSheet()
    style_normal = styles["Normal"]
    style_normal.fontName = 'IPAGothic'  # フォントを設定
    style_normal.fontSize = 8  # フォントサイズを設定
    style_normal.leading = 12.5  # 行間を設定

    # Paragraphを作成
    paragraph = Paragraph(long_text, style_normal)

    # Frameを作成してParagraphを配置
    frame = Frame(x_position, y_position, frame_width, frame_height, showBoundary=1)
    while True:
        story = [paragraph]
        frame.addFromList(story, c)
        if not story:
            break
        long_text = long_text[:-1]
        paragraph = Paragraph(long_text, style_normal)
    return

@app.route('/download_pdf', methods=['GET'])
def download_pdf():
    # 既存の背景PDFファイルを読み込む
    background_pdf_path = "./static/background.pdf"  # 背景となるPDFのパスを指定
    background_pdf = PdfReader(background_pdf_path)
    background_page = background_pdf.pages[0]  # 背景として使用するページを指定

    # メモリ上に新しいPDFを生成
    pdf_buffer = BytesIO()

    # フォントを登録
    pdfmetrics.registerFont(TTFont('IPAGothic', './static/ipaexg.ttf'))

    # ReportLabのCanvasを作成
    c = canvas.Canvas(pdf_buffer, pagesize=landscape(A3))

    # 日付
    c.drawString(150 * mm, 285 * mm, str(datetime.datetime.now().year-2018))
    c.drawString(163 * mm, 285 * mm, str(datetime.datetime.now().month))
    c.drawString(177 * mm, 285 * mm, str(datetime.datetime.now().day))
    
    # firestore setup
    record_ref = db.collection(session['user']['localId']).document('sougyou').collection('setup').document('data')
    doc = record_ref.get()
    data = doc.to_dict() if doc.exists else {}
    c.setFont('IPAGothic', 12)
    c.drawString(120 * mm, 275 * mm, data.get('familyname')+data.get('firstname'))
    
    # firestore yourself
    record_ref = db.collection(session['user']['localId']).document('sougyou').collection('yourself').document('data')
    doc = record_ref.get()
    data = doc.to_dict() if doc.exists else {}
    c.setFont('IPAGothic', 9)
    if data.get('record_year_1') != '':
        c.drawString(22 * mm, 236 * mm, data.get('record_year_1')+'年'+data.get('record_month_1')+'月')
        c.drawString(50 * mm, 236 * mm, data.get('record_detail_1'))
    if data.get('record_year_2') != '':
        c.drawString(22 * mm, 231.5 * mm, data.get('record_year_2')+'年'+data.get('record_month_2')+'月')
        c.drawString(50 * mm, 231.5 * mm, data.get('record_detail_2'))
    if data.get('record_year_3') != '':
        c.drawString(22 * mm, 227 * mm, data.get('record_year_3')+'年'+data.get('record_month_3')+'月')
        c.drawString(50 * mm, 227 * mm, data.get('record_detail_3'))
    if data.get('record_year_4') != '':
        c.drawString(22 * mm, 222.5 * mm, data.get('record_year_4')+'年'+data.get('record_month_4')+'月')
        c.drawString(50 * mm, 222.5 * mm, data.get('record_detail_4'))
    if data.get('record_year_5') != '':
        c.drawString(22 * mm, 218 * mm, data.get('record_year_5')+'年'+data.get('record_month_5')+'月')
        c.drawString(50 * mm, 218 * mm, data.get('record_detail_5'))
    c.setFont('IPAGothic', 12)
    if data.get('status_experience') == 'status_experience_0':
        c.drawString(48.5 * mm, 208.5 * mm, '■')
    if data.get('status_experience') == 'status_experience_1':
        c.drawString(48.5 * mm, 203.5 * mm, '■')
        c.setFont('IPAGothic', 9)
        c.drawString(167 * mm, 203.5 * mm, data.get('experience_detail'))
    if data.get('status_experience') == 'status_experience_2':
        c.drawString(48.5 * mm, 198.5 * mm, '■')
        c.setFont('IPAGothic', 9)
        c.drawString(48.5 * mm, 206 * mm, data.get('experience_when'))
    c.setFont('IPAGothic', 12)
    if data.get('status_license') == 'status_license_0':
        c.drawString(48.5 * mm, 194.5 * mm, '■')
    #if data.get('status_license') == 'status_license_1':
        # c.drawString(48.5 * mm, 188.5 * mm, '■')
    c.setFont('IPAGothic', 12)
    if data.get('status_patent') == 'status_patent_0':
        c.drawString(48.5 * mm, 190 * mm, '■')
    #if data.get('status_patent') == 'status_patent_1':
        # c.drawString(48.5 * mm, 183.5 * mm, '■')
    # motivation paragraph    
    # 絶対位置を指定してFrameを作成（x, y, 幅, 高さ）
    frame_width = 177 * mm  # 横幅を指定
    frame_height = 25 * mm  # 高さを指定
    x_position = 20 * mm  # 左から1インチ
    y_position = 243 * mm  # 下から9インチ（上に配置される）
    long_text = data.get('motivation_detail', '（なし）')
    add_paragraph(x_position, y_position, frame_width, frame_height, long_text, c)

    # firestore business
    record_ref = db.collection(session['user']['localId']).document('sougyou').collection('business').document('data')
    doc = record_ref.get()
    data = doc.to_dict() if doc.exists else {}
    # business_detail paragraph    
    # 絶対位置を指定してFrameを作成（x, y, 幅, 高さ）
    frame_width = 152 * mm  # 横幅を指定
    frame_height = 12 * mm  # 高さを指定
    x_position = 47 * mm  # 左から1インチ
    y_position = 174 * mm  # 下から9インチ（上に配置される）
    long_text = data.get('business_detail', '（なし）')
    add_paragraph(x_position, y_position, frame_width, frame_height, long_text, c)
    c.setFont('IPAGothic', 9)
    if data.get('product_1_detail') != '':
        c.drawString(54 * mm, 172 * mm, data.get('product_1_detail'))
        c.drawString(180 * mm, 172 * mm, data.get('product_1_share'))
    if data.get('product_2_detail') != '':
        c.drawString(54 * mm, 167.5 * mm, data.get('product_2_detail'))
        c.drawString(180 * mm, 167.5 * mm, data.get('product_2_share'))
    if data.get('product_3_detail') != '':
        c.drawString(54 * mm, 163 * mm, data.get('product_3_detail'))
        c.drawString(180 * mm, 163 * mm, data.get('product_3_share'))
    # strength_detail paragraph    
    # 絶対位置を指定してFrameを作成（x, y, 幅, 高さ）
    frame_width = 152 * mm  # 横幅を指定
    frame_height = 17 * mm  # 高さを指定
    x_position = 47 * mm  # 左から1インチ
    y_position = 137 * mm  # 下から9インチ（上に配置される）
    long_text = data.get('strength_detail', '（なし）')
    add_paragraph(x_position, y_position, frame_width, frame_height, long_text, c)
    # target_detail paragraph    
    # 絶対位置を指定してFrameを作成（x, y, 幅, 高さ）
    frame_width = 152 * mm  # 横幅を指定
    frame_height = 17 * mm  # 高さを指定
    x_position = 47 * mm  # 左から1インチ
    y_position = 123 * mm  # 下から9インチ（上に配置される）
    long_text = data.get('target_detail', '（なし）')
    add_paragraph(x_position, y_position, frame_width, frame_height, long_text, c)
    # competitor_detail paragraph    
    # 絶対位置を指定してFrameを作成（x, y, 幅, 高さ）
    frame_width = 152 * mm  # 横幅を指定
    frame_height = 17 * mm  # 高さを指定
    x_position = 47 * mm  # 左から1インチ
    y_position = 111 * mm  # 下から9インチ（上に配置される）
    long_text = data.get('competitor_detail', '（なし）')
    add_paragraph(x_position, y_position, frame_width, frame_height, long_text, c)
    
    # firestore partner
    record_ref = db.collection(session['user']['localId']).document('sougyou').collection('partner').document('data')
    doc = record_ref.get()
    data = doc.to_dict() if doc.exists else {}
    c.setFont('IPAGothic', 9)

    # firestore funds
    record_ref = db.collection(session['user']['localId']).document('sougyou').collection('funds').document('data')
    doc = record_ref.get()
    data = doc.to_dict() if doc.exists else {}
    c.setFont('IPAGothic', 9)

    # firestore others
    record_ref = db.collection(session['user']['localId']).document('sougyou').collection('others').document('data')
    doc = record_ref.get()
    data = doc.to_dict() if doc.exists else {}
    c.setFont('IPAGothic', 9)
    if data.get('debt_1_from') != '':
        c.drawString(216 * mm, 236 * mm, data.get('debt_1_from'))
        c.setFont('IPAGothic', 12)
        match data.get('debt_1_usage'):
            case 'debt_1_usage_1':
                c.drawString(262 * mm, 236 * mm, '■')
            case 'debt_1_usage_2':
                c.drawString(276 * mm, 236 * mm, '■')
            case 'debt_1_usage_3':
                c.drawString(290 * mm, 236 * mm, '■')
            case 'debt_1_usage_4':
                c.drawString(299 * mm, 236 * mm, '■')
            case 'debt_1_usage_5':
                c.drawString(313 * mm, 236 * mm, '■')
            case 'debt_1_usage_6':
                c.drawString(326 * mm, 236 * mm, '■')
        c.setFont('IPAGothic', 9)
        debt_1_amount=int(float(data.get('debt_1_amount',0))/10000)
        print(debt_1_amount)
        debt_1_annual=int(float(data.get('debt_1_annual',0))/10000)
        c.drawString(347 * mm, 236 * mm, str(debt_1_amount))
        c.drawString(372 * mm, 236 * mm, str(debt_1_annual))
    if data.get('debt_2_from') != '':
        c.drawString(216 * mm, 231.5 * mm, data.get('debt_2_from'))
        c.setFont('IPAGothic', 12)
        match data.get('debt_2_usage'):
            case 'debt_2_usage_1':
                c.drawString(262 * mm, 231.5 * mm, '■')
            case 'debt_2_usage_2':
                c.drawString(276 * mm, 231.5 * mm, '■')
            case 'debt_2_usage_3':
                c.drawString(290 * mm, 231.5 * mm, '■')
            case 'debt_2_usage_4':
                c.drawString(299 * mm, 231.5 * mm, '■')
            case 'debt_2_usage_5':
                c.drawString(313 * mm, 231.5 * mm, '■')
            case 'debt_2_usage_6':
                c.drawString(326 * mm, 231.5 * mm, '■')
        c.setFont('IPAGothic', 9)
        debt_1_amount=int(float(data.get('debt_2_amount',0))/10000)
        print(debt_1_amount)
        debt_1_annual=int(float(data.get('debt_2_annual',0))/10000)
        c.drawString(347 * mm, 231.5 * mm, str(debt_1_amount))
        c.drawString(372 * mm, 231.5 * mm, str(debt_1_annual))
    if data.get('debt_3_from') != '':
        c.drawString(216 * mm, 227 * mm, data.get('debt_3_from'))
        c.setFont('IPAGothic', 12)
        match data.get('debt_3_usage'):
            case 'debt_3_usage_1':
                c.drawString(262 * mm, 227 * mm, '■')
            case 'debt_3_usage_2':
                c.drawString(276 * mm, 227 * mm, '■')
            case 'debt_3_usage_3':
                c.drawString(290 * mm, 227 * mm, '■')
            case 'debt_3_usage_4':
                c.drawString(299 * mm, 227 * mm, '■')
            case 'debt_3_usage_5':
                c.drawString(313 * mm, 227 * mm, '■')
            case 'debt_3_usage_6':
                c.drawString(326 * mm, 227 * mm, '■')
        c.setFont('IPAGothic', 9)
        debt_1_amount=int(float(data.get('debt_3_amount',0))/10000)
        print(debt_1_amount)
        debt_1_annual=int(float(data.get('debt_3_annual',0))/10000)
        c.drawString(347 * mm, 227 * mm, str(debt_1_amount))
        c.drawString(372 * mm, 227 * mm, str(debt_1_annual))
    # appeal paragraph    
    # 絶対位置を指定してFrameを作成（x, y, 幅, 高さ）
    frame_width = 177 * mm  # 横幅を指定
    frame_height = 20 * mm  # 高さを指定
    x_position = 214 * mm  # 左から1インチ
    y_position = 20 * mm  # 下から9インチ（上に配置される）
    long_text = data.get('appeal', '（なし）')
    add_paragraph(x_position, y_position, frame_width, frame_height, long_text, c)

    # PDFを保存
    c.showPage()
    c.save()

    # バッファを最初に戻す
    pdf_buffer.seek(0)

    # 新しいPDFを読み込む
    new_pdf = PdfReader(pdf_buffer)
    new_page = new_pdf.pages[0]

    # PdfWriterを使って背景と新しいページを合成
    output_pdf = PdfWriter()
    background_page.merge_page(new_page)

    # 合成したページを追加
    output_pdf.add_page(background_page)

    # 出力用のバッファを作成
    output_pdf_buffer = BytesIO()
    output_pdf.write(output_pdf_buffer)
    output_pdf_buffer.seek(0)

    # PDFをダウンロードとして返す
    return send_file(output_pdf_buffer, as_attachment=False, download_name='final_output_with_position.pdf', mimetype='application/pdf')

# アプリケーションのエントリーポイント
if __name__ == '__main__':
    app.run(debug=True)