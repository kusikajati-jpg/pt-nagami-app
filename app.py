from datetime import datetime
import io
import json
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import pandas as pd
import streamlit as st

# --- IMPORT WAJIB REPORTLAB UNTUK PDF ---
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Konfigurasi Halaman Web
st.set_page_config(
    page_title="Aplikasi PT Nata Gatra Mitra (NAGAMI)",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- KONFIGURASI LOGIN & USER ROLES ---
USER_CREDENTIALS = {
    "admin": {"password": "nagami2026", "role": "Admin / Pimpinan"},
    "hidayat": {"password": "nagami123", "role": "Staff / Marketing"},
}

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "user_role" not in st.session_state:
    st.session_state.user_role = ""

# Halaman Login
if not st.session_state.logged_in:
    logo_path = "logo_nagami.png"
    if os.path.exists(logo_path):
        col_img1, col_img2, col_img3 = st.columns([1, 1, 1])
        with col_img2:
            st.image(logo_path, width=200)

    st.markdown(
        "<h2 style='text-align: center; color: #9b2c2c;'>🔐 LOGIN SISTEM PT NATA GATRA MITRA</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align: center;'>Silakan masukkan Username dan Password Anda.</p>",
        unsafe_allow_html=True,
    )

    col_l1, col_l2, col_l3 = st.columns([1, 1.5, 1])
    with col_l2:
        with st.form("login_form"):
            input_user = st.text_input("Username")
            input_pass = st.text_input("Password", type="password")
            submit_login = st.form_submit_button("🔑 Masuk Aplikasi", use_container_width=True)

            if submit_login:
                if input_user in USER_CREDENTIALS and USER_CREDENTIALS[input_user]["password"] == input_pass:
                    st.session_state.logged_in = True
                    st.session_state.username = input_user
                    st.session_state.user_role = USER_CREDENTIALS[input_user]["role"]
                    st.success("Login berhasil! Memuat aplikasi...")
                    st.rerun()
                else:
                    st.error("Username atau Password salah!")
    st.stop()


# Nama File Database JSON
FILE_KLIEN = "master_klien.json"
FILE_SUPPLIER = "master_supplier.json"
FILE_BARANG = "master_barang.json"
FILE_PEMBELIAN = "master_pembelian.json"
FILE_INVOICE = "riwayat_invoice.json"
FILE_CONFIG = "template_config.json"
FILE_COUNTER = "counter_dokumen.json"
FILE_STOCK_CARD = "stock_card.json"
FILE_PROFIL = "profil_perusahaan.json"
FILE_SMTP = "smtp_config.json"
FILE_LOG = "audit_log.json"

DEFAULT_CONFIG = {
    "Invoice": {
        "judul_dokumen": "INVOICE",
        "tampilkan_customer": True,
        "tampilkan_harga": True,
        "kolom_tabel": ["No", "Description", "Qty", "Unit", "Unit Price", "Total Price"],
        "lebar_kolom": [28, 245, 42, 55, 95, 70],
        "catatan_footer": "Pembayaran dianggap lunas apabila Cek/Giro/Transfer telah dibukukan di Bank kami sbb:<br/><b>BANK MANDIRI, KCP BEKASI PEJUANG</b><br/><b>A/N : PT NATA GATRA MITRA</b><br/><b>A/C : 156-00-2832490-5</b>",
    },
    "Quotation / Penawaran": {
        "judul_dokumen": "QUOTATION",
        "tampilkan_customer": True,
        "tampilkan_harga": True,
        "kolom_tabel": ["No", "Description", "QTY", "Satuan", "Unit Price", "Total Price"],
        "lebar_kolom": [28, 245, 42, 55, 95, 70],
        "catatan_footer": "Thank you for your kind attention and we are looking forward to your order soon.",
    },
    "Surat Jalan": {
        "judul_dokumen": "SURAT JALAN",
        "tampilkan_customer": True,
        "tampilkan_harga": False,
        "kolom_tabel": ["No.", "Nama Barang", "QTY", "Satuan", "KETERANGAN"],
        "lebar_kolom": [25, 295, 35, 50, 120],
        "catatan_footer": "Barang-barang tersebut telah diterima dalam keadaan baik dan cukup.",
    },
    "Purchase Order": {
        "judul_dokumen": "PURCHASE ORDER",
        "tampilkan_customer": True,
        "tampilkan_harga": True,
        "kolom_tabel": ["No", "Nama Barang", "QTY", "Satuan", "KETERANGAN", "Total Price"],
        "lebar_kolom": [28, 245, 42, 55, 95, 70],
        "catatan_footer": "Harap kirimkan barang sesuai dengan spesifikasi di atas.",
    },
    "Tanda Terima": {
        "judul_dokumen": "BUKTI TANDA TERIMA",
        "tampilkan_customer": True,
        "tampilkan_harga": True,
        "kolom_tabel": ["No.", "FAKTUR / INVOICE NO.", "TANGGAL", "JUMLAH (RP)"],
        "lebar_kolom": [30, 200, 110, 170],
        "catatan_footer": "Telah diterima dokumen / pembayaran dengan baik dan sah.",
    },
}

DEFAULT_PROFIL = {
    "nama_perusahaan": "PT NATA GATRA MITRA",
    "tagline": "Anagata Business Loft, Unit IX.7 No.18",
    "alamat": "Harapan Indah, Setia Asih, Taruma Jaya<br/>Bekasi - Jawa Barat 17612",
    "email": "marketing@nagami.co.id",
    "telp": "021-0000000",
    "direktur": "Hidayat",
}

DEFAULT_SMTP = {
    "server": "smtp.gmail.com",
    "port": 465,
    "sender": "marketing@nagami.co.id",
    "password": "",
}


def load_data(filename, default=None):
    if default is None:
        default = []
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default
    return default


def save_data(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def log_activity(aksi, detail):
    logs = load_data(FILE_LOG, [])
    logs.append({
        "waktu": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
        "user": st.session_state.get("username", "system"),
        "aksi": aksi,
        "detail": detail,
    })
    save_data(FILE_LOG, logs)


def _stock_float(value, default=0.0):
    try:
        return float(value or 0)
    except (ValueError, TypeError):
        return float(default)


def _normalize_barang_record(item):
    item = dict(item) if isinstance(item, dict) else {}
    item["nama"] = str(item.get("nama", "")).strip()
    item["harga"] = _stock_float(item.get("harga", 0))
    item["stok"] = int(_stock_float(item.get("stok", 0)))
    if "stok_awal" not in item:
        item["stok_awal"] = item["stok"]
    else:
        item["stok_awal"] = int(_stock_float(item.get("stok_awal", item["stok"])))
    if "kelola_stok" not in item:
        item["kelola_stok"] = True
    else:
        item["kelola_stok"] = bool(item.get("kelola_stok"))
    return item


def load_stock_card():
    data = load_data(FILE_STOCK_CARD, [])
    return data if isinstance(data, list) else []


def _stock_opening_exists(ledger, nama_barang):
    return any(
        isinstance(x, dict) and x.get("barang") == nama_barang and x.get("jenis") == "SALDO AWAL"
        for x in ledger
    )


def ensure_stock_opening_ledger():
    ledger = load_stock_card()
    changed = False
    for barang in data_barang:
        nama = barang.get("nama", "")
        if not nama:
            continue
        if not _stock_opening_exists(ledger, nama):
            saldo = int(barang.get("stok", 0) or 0)
            ledger.append({
                "id": f"OPEN-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                "tanggal": datetime.now().strftime("%d-%m-%Y"),
                "jenis": "SALDO AWAL",
                "referensi": "OPENING",
                "barang": nama,
                "qty_masuk": saldo if saldo > 0 else 0,
                "qty_keluar": 0,
                "saldo": saldo,
                "user": st.session_state.get("username", "system"),
                "keterangan": "Saldo stok awal saat migrasi",
            })
            changed = True
    if changed:
        save_data(FILE_STOCK_CARD, ledger)
    return ledger


def _find_barang(nama_barang):
    for barang in data_barang:
        if str(barang.get("nama", "")).strip() == str(nama_barang).strip():
            return barang
    return None


def _qty_stok_keluar(items):
    total = {}
    for item in items or []:
        if not isinstance(item, dict):
            continue
        nama = str(item.get("nama", "")).strip()
        barang = _find_barang(nama)
        if not barang or not barang.get("kelola_stok", True):
            continue
        qty = int(_stock_float(item.get("qty", 0)))
        if qty > 0:
            total[nama] = total.get(nama, 0) + qty
    return total


def validate_stock_out(items):
    kebutuhan = _qty_stok_keluar(items)
    errors = []
    for nama, qty in kebutuhan.items():
        barang = _find_barang(nama)
        stok = int(barang.get("stok", 0)) if barang else 0
        if stok < qty:
            errors.append(f"{nama}: tersedia {stok}, dibutuhkan {qty}")
    return errors, kebutuhan


def apply_stock_movement(
    nama_barang, qty_masuk=0, qty_keluar=0, jenis="ADJUSTMENT",
    referensi="", keterangan="", tanggal=None
):
    barang = _find_barang(nama_barang)
    if not barang:
        return False, f"Barang '{nama_barang}' tidak ditemukan."
    qty_masuk = int(_stock_float(qty_masuk))
    qty_keluar = int(_stock_float(qty_keluar))
    if qty_masuk < 0 or qty_keluar < 0 or (qty_masuk and qty_keluar):
        return False, "Qty stok tidak valid."
    if not barang.get("kelola_stok", True):
        return True, ""
    stok_lama = int(barang.get("stok", 0))
    stok_baru = stok_lama + qty_masuk - qty_keluar
    if stok_baru < 0:
        return False, f"Stok '{nama_barang}' tidak mencukupi."
    barang["stok"] = stok_baru
    ledger = load_stock_card()
    ledger.append({
        "id": f"MOV-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "tanggal": tanggal or datetime.now().strftime("%d-%m-%Y"),
        "jenis": jenis,
        "referensi": referensi,
        "barang": nama_barang,
        "qty_masuk": qty_masuk,
        "qty_keluar": qty_keluar,
        "saldo": stok_baru,
        "user": st.session_state.get("username", "system"),
        "keterangan": keterangan,
    })
    save_data(FILE_BARANG, data_barang)
    save_data(FILE_STOCK_CARD, ledger)
    return True, ""


def apply_stock_out_for_document(items, nomor_dokumen, tanggal):
    errors, kebutuhan = validate_stock_out(items)
    if errors:
        return False, errors
    for nama, qty in kebutuhan.items():
        ok, msg = apply_stock_movement(
            nama,
            qty_keluar=qty,
            jenis="STOK KELUAR",
            referensi=nomor_dokumen,
            keterangan="Pengeluaran barang melalui Surat Jalan",
            tanggal=tanggal,
        )
        if not ok:
            return False, [msg]
    return True, []


def _prefix_dokumen(jenis_dok):
    jenis = str(jenis_dok or "").strip()
    if "Invoice" in jenis:
        return "INV-NGM"
    if "Quotation" in jenis:
        return "QT-NGM"
    if "Surat Jalan" in jenis:
        return "SJ-NGM"
    if "Purchase Order" in jenis:
        return "PO-NGM"
    if "Tanda Terima" in jenis:
        return "TT-NGM"
    return "DOC-NGM"


def _infer_jenis_dokumen(record):
    if not isinstance(record, dict):
        return "Invoice"
    jenis = record.get("jenis_dokumen") or record.get("jenis_dok")
    if jenis:
        return str(jenis)
    nomor = str(record.get("no_dokumen") or record.get("no_inv") or "").upper()
    if "/QT-NGM/" in nomor:
        return "Quotation / Penawaran"
    if "/SJ-NGM/" in nomor:
        return "Surat Jalan"
    if "/PO-NGM/" in nomor:
        return "Purchase Order"
    if "/TT-NGM/" in nomor:
        return "Tanda Terima"
    return "Invoice"


def normalize_invoice_history(history):
    if not isinstance(history, list):
        return [], True
    changed = False
    normalized = []

    for record in history:
        if not isinstance(record, dict):
            changed = True
            continue

        item = dict(record)
        jenis = _infer_jenis_dokumen(item)
        nomor = str(item.get("no_dokumen") or item.get("no_inv") or "")
        items = item.get("items", [])
        if not isinstance(items, list):
            items = []

        subtotal_default = sum(
            float(i.get("total", 0) or 0) for i in items if isinstance(i, dict)
        )
        subtotal = float(item.get("subtotal", subtotal_default) or 0)
        discount = float(item.get("discount", 0) or 0)
        ppn = float(item.get("ppn", 0) or 0)
        pph23 = float(item.get("pph23", 0) or 0)
        dpp_lainnya = float(item.get("dpp_lainnya", 0) or 0)

        defaults = {
            "jenis_dokumen": jenis,
            "no_dokumen": nomor,
            "no_inv": nomor,
            "tanggal": item.get("tanggal", datetime.now().strftime("%d-%m-%Y")),
            "klien": item.get("klien", ""),
            "status": item.get("status", "Belum Lunas (Piutang)"),
            "items": items,
            "subtotal": subtotal,
            "discount": discount,
            "pph23": pph23,
            "dpp_lainnya": dpp_lainnya,
            "ppn": ppn,
            "label_ppn": item.get("label_ppn", "*Belum termasuk PPN 11%"),
            "pilihan_ppn": item.get("pilihan_ppn", "PPN 11%" if ppn > 0 else "Tanpa PPN (0%)"),
            "no_sj": item.get("no_sj", "(Kosong / Tanpa Referensi)"),
            "no_po": item.get("no_po", "(Kosong / Tanpa Referensi)"),
            "no_quo": item.get("no_quo", "(Kosong / Tanpa Referensi)"),
            "pic": item.get("pic", "Bpk. Pimpinan"),
            "division": item.get("division", "PURCHASING"),
            "subject": item.get("subject", "PENGADAAN BARANG / JASA"),
            "term_payment": item.get("term_payment", "30 day after invoice"),
            "validity_term": item.get("validity_term", "1 week"),
            "note_text": item.get("note_text", "Prices are not fixed depending on the materials/goods available"),
            "email_target": item.get("email_target", "marketing@nagami.co.id"),
            "tanda_terima_invoice_no": item.get("tanda_terima_invoice_no"),
            "tanda_terima_invoice_date": item.get("tanda_terima_invoice_date"),
            "tanda_terima_amount": float(item.get("tanda_terima_amount", item.get("grand_total", 0)) or 0),
            "penerima_nama": item.get("penerima_nama", "Customer / Penerima"),
            "grand_total": float(
                item.get("grand_total", subtotal - discount + ppn - pph23 + dpp_lainnya) or 0
            ),
        }

        for key, value in defaults.items():
            if key not in item:
                item[key] = value
                changed = True
        normalized.append(item)

    return normalized, changed


def _nomor_ke_angka(nomor, prefix, tahun):
    try:
        bagian = str(nomor or "").split("/")
        if len(bagian) >= 4 and bagian[1] == prefix and bagian[3] == tahun:
            return int(bagian[0])
    except (ValueError, TypeError):
        pass
    return 0


def _load_counter_dokumen():
    data = load_data(FILE_COUNTER, {})
    return data if isinstance(data, dict) else {}


def _sync_counter_dokumen():
    counters = _load_counter_dokumen()
    for inv in data_invoice_history:
        jenis = _infer_jenis_dokumen(inv)
        prefix = _prefix_dokumen(jenis)
        nomor = inv.get("no_dokumen") or inv.get("no_inv", "")
        bagian = str(nomor).split("/")
        if len(bagian) >= 4:
            key = f"{prefix}/{bagian[3]}"
            nomor_urut = _nomor_ke_angka(nomor, prefix, bagian[3])
            if nomor_urut > int(counters.get(key, 0) or 0):
                counters[key] = nomor_urut
    save_data(FILE_COUNTER, counters)
    return counters


def nomor_dokumen_sudah_ada(nomor, ignore_index=None):
    nomor = str(nomor or "").strip()
    if not nomor:
        return False
    for idx, inv in enumerate(data_invoice_history):
        if ignore_index is not None and idx == ignore_index:
            continue
        nomor_lama = str(inv.get("no_dokumen") or inv.get("no_inv") or "").strip()
        if nomor_lama.lower() == nomor.lower():
            return True
    return False


def generate_auto_no_dokumen(jenis_dok="Invoice"):
    now = datetime.now()
    romawi_bulan = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
    rom_bln = romawi_bulan[now.month]
    thn_2digit = now.strftime("%y")
    prefix = _prefix_dokumen(jenis_dok)
    key = f"{prefix}/{thn_2digit}"

    counters = _load_counter_dokumen()
    current = int(counters.get(key, 0) or 0)
    for inv in data_invoice_history:
        nomor = inv.get("no_dokumen") or inv.get("no_inv", "")
        current = max(current, _nomor_ke_angka(nomor, prefix, thn_2digit))

    return f"{current + 1:03d}/{prefix}/{rom_bln}/{thn_2digit}"


def reserve_no_dokumen(nomor, jenis_dok):
    nomor = str(nomor or "").strip()
    if not nomor:
        return
    prefix = _prefix_dokumen(jenis_dok)
    tahun = datetime.now().strftime("%y")
    counters = _load_counter_dokumen()
    nomor_urut = _nomor_ke_angka(nomor, prefix, tahun)
    if nomor_urut > 0:
        key = f"{prefix}/{tahun}"
        counters[key] = max(int(counters.get(key, 0) or 0), nomor_urut)
        save_data(FILE_COUNTER, counters)


def init_config_file():
    if not os.path.exists(FILE_CONFIG):
        save_data(FILE_CONFIG, DEFAULT_CONFIG)
    if not os.path.exists(FILE_PROFIL):
        save_data(FILE_PROFIL, DEFAULT_PROFIL)
    if not os.path.exists(FILE_SMTP):
        save_data(FILE_SMTP, DEFAULT_SMTP)


init_config_file()

data_klien = load_data(FILE_KLIEN, [])
data_supplier = load_data(FILE_SUPPLIER, [])
raw_barang = load_data(FILE_BARANG, [])
data_barang = []
for b in raw_barang:
    if isinstance(b, dict):
        data_barang.append(_normalize_barang_record(b))
if data_barang != raw_barang:
    save_data(FILE_BARANG, data_barang)

data_pembelian = load_data(FILE_PEMBELIAN, [])
data_invoice_history = load_data(FILE_INVOICE, [])
data_invoice_history, history_changed = normalize_invoice_history(data_invoice_history)
if history_changed:
    save_data(FILE_INVOICE, data_invoice_history)
_sync_counter_dokumen()
ensure_stock_opening_ledger()


def terbilang(nilai):
    nilai = int(nilai)
    if nilai < 0:
        return "minus " + terbilang(-nilai)
    angka = [
        "", "Satu", "Dua", "Tiga", "Empat", "Lima", "Enam", "Tujuh",
        "Delapan", "Sembilan", "Sepuluh", "Sebelas",
    ]
    if nilai < 12:
        return " " + angka[nilai]
    elif nilai < 20:
        return terbilang(nilai - 10) + " Belas"
    elif nilai < 100:
        return terbilang(nilai // 10) + " Puluh" + terbilang(nilai % 10)
    elif nilai < 200:
        return " Seratus" + terbilang(nilai - 100)
    elif nilai < 1000:
        return terbilang(nilai // 100) + " Ratus" + terbilang(nilai % 100)
    elif nilai < 2000:
        return " Seribu" + terbilang(nilai - 1000)
    elif nilai < 1000000:
        return terbilang(nilai // 1000) + " Ribu" + terbilang(nilai % 1000)
    elif nilai < 1000000000:
        return terbilang(nilai // 1000000) + " Juta" + terbilang(nilai % 1000000)
    elif nilai < 1000000000000:
        return terbilang(nilai // 1000000000) + " Milyar" + terbilang(nilai % 1000000000)
    else:
        return ""


def format_terbilang(nilai):
    if nilai == 0:
        return "Nol Rupiah"
    hasil = terbilang(nilai).strip()
    return f"{hasil} Rupiah"


def kirim_email_pdf(penerima, subjek, pesan, pdf_bytes, nama_file):
    smtp_config = load_data(FILE_SMTP, DEFAULT_SMTP)
    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_config.get("sender", "marketing@nagami.co.id")
        msg["To"] = penerima
        msg["Subject"] = subjek

        msg.attach(MIMEText(pesan, "plain"))
        part = MIMEApplication(pdf_bytes, Name=nama_file)
        part["Content-Disposition"] = f'attachment; filename="{nama_file}"'
        msg.attach(part)

        port = int(smtp_config.get("port", 465))
        server_address = smtp_config.get("server", "smtp.gmail.com")

        if port == 465:
            server = smtplib.SMTP_SSL(server_address, port)
        else:
            server = smtplib.SMTP(server_address, port)
            server.starttls()

        server.login(smtp_config.get("sender"), smtp_config.get("password"))
        server.sendmail(smtp_config.get("sender"), penerima, msg.as_string())
        server.quit()
        return True, "Email berhasil dikirim!"
    except Exception as e:
        return False, f"Gagal mengirim email: {str(e)}"


# --- FUNGSI PEMBUATAN PDF ---
def buat_pdf_bytes(
    jenis_dok,
    no_inv,
    no_sj,
    tanggal,
    no_po,
    no_quo,
    klien,
    telp,
    email,
    pic,
    division,
    subject,
    term_payment,
    validity_term,
    note_text,
    email_target,
    items,
    subtotal,
    discount,
    pph23,
    dpp_lainnya,
    ppn,
    label_ppn,
    grand_total,
    tanda_terima_invoice_no=None,
    tanda_terima_invoice_date=None,
    tanda_terima_amount=None,
    penerima_nama="Customer / Penerima",
    po_loco_to="PT. Nata Gatra Mitra",
    po_delivery="Indent 2-3 week",
    po_prepared_by="Procurement",
    po_authorized_by="Direktur",
    po_notes=None,
):
    config_data = load_data(FILE_CONFIG, DEFAULT_CONFIG)
    if not isinstance(config_data, dict):
        config_data = DEFAULT_CONFIG
    cfg = config_data.get(jenis_dok, config_data.get("Invoice", {}))
    if not isinstance(cfg, dict):
        cfg = DEFAULT_CONFIG.get("Invoice", {})

    judul_dok = cfg.get("judul_dokumen", jenis_dok.upper())
    tampilkan_customer = cfg.get("tampilkan_customer", True)
    tampilkan_harga = cfg.get("tampilkan_harga", True)
    kolom_header = cfg.get("kolom_tabel", ["No.", "Nama Barang", "QTY", "Satuan", "KETERANGAN"])
    lebar_kol = cfg.get("lebar_kolom", [25, 295, 35, 50, 120])

    catatan_footer = cfg.get("catatan_footer", "")
    if not catatan_footer or catatan_footer.strip() == "":
        if jenis_dok == "Invoice":
            catatan_footer = "Pembayaran dianggap lunas apabila Cek/Giro/Transfer telah dibukukan di Bank kami sbb:<br/><b>BANK MANDIRI, KCP BEKASI PEJUANG</b><br/><b>A/N : PT NATA GATRA MITRA</b><br/><b>A/C : 156-00-2832490-5</b>"
        elif jenis_dok == "Quotation / Penawaran":
            catatan_footer = "Thank you for your kind attention and we are looking forward to your order soon."
        elif jenis_dok == "Surat Jalan":
            catatan_footer = "Barang-barang tersebut telah diterima dalam keadaan baik dan cukup."
        else:
            catatan_footer = "Terima kasih atas kerjasamanya."

    logo_path = "logo_nagami.png"
    profil_pdf = load_data(FILE_PROFIL, DEFAULT_PROFIL)
    c_nama = profil_pdf.get("nama_perusahaan", "PT NATA GATRA MITRA")
    c_tagline = profil_pdf.get("tagline", "Anagata Business Loft, Unit IX.7 No.18")
    c_alamat = profil_pdf.get("alamat", "Harapan Indah, Setia Asih, Taruma Jaya<br/>Bekasi - Jawa Barat 17612")
    c_email = profil_pdf.get("email", "marketing@nagami.co.id")
    c_telp = profil_pdf.get("telp", "021-0000000")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )
    story = []
    styles = getSampleStyleSheet()
    normal_style = styles["Normal"]

    table_cell_style = ParagraphStyle("TableCellStyle", parent=normal_style, fontSize=8, leading=11)
    table_desc_quotation = ParagraphStyle("TableDescQT", parent=normal_style, fontSize=8, leading=11)

    left_header = []
    if logo_path and os.path.exists(logo_path):
        left_header.append(Image(logo_path, width=110, height=42))
        left_header.append(Spacer(1, 4))
    left_header.append(
        Paragraph(
            f"<b><font size=13 color='#9b2c2c'>{c_nama}</font></b><br/>{c_tagline}<br/>{c_alamat}<br/>Email: {c_email} | Telp: {c_telp}",
            ParagraphStyle("Co", parent=normal_style, fontSize=8, leading=11),
        )
    )

    style_judul_tengah = ParagraphStyle(
        "JdlTengah", parent=normal_style, fontSize=20, leading=24,
        fontName="Helvetica-Bold", textColor=colors.HexColor("#9b2c2c"), alignment=1
    )
    judul_formatted = f"<u><b>{judul_dok}</b></u>"

    if jenis_dok == "Surat Jalan":
        right_header_data = [
            [Paragraph(judul_formatted, style_judul_tengah), "", ""],
            [Paragraph("<b>Date</b>", normal_style), Paragraph(":", normal_style), Paragraph(f"{tanggal}", normal_style)],
            [Paragraph("<b>No. SJ</b>", normal_style), Paragraph(":", normal_style), Paragraph(f"{no_inv}", normal_style)],
        ]
        if no_po and no_po != "(Kosong / Tanpa Referensi)":
            right_header_data.append([Paragraph("<b>No. PO</b>", normal_style), Paragraph(":", normal_style), Paragraph(f"{no_po}", normal_style)])
        else:
            right_header_data.append([Paragraph("<b>No. PO</b>", normal_style), Paragraph(":", normal_style), Paragraph("-", normal_style)])
    elif jenis_dok in ["Tanda Terima", "Quotation / Penawaran"]:
        right_header_data = [
            [Paragraph(judul_formatted, style_judul_tengah), "", ""],
            [Paragraph("<b>Date</b>", normal_style), Paragraph(":", normal_style), Paragraph(f"{tanggal}", normal_style)],
            [Paragraph("<b>No.</b>", normal_style), Paragraph(":", normal_style), Paragraph(f"{no_inv}", normal_style)],
        ]
    elif jenis_dok == "Purchase Order":
        right_header_data = [
            [Paragraph(judul_formatted, style_judul_tengah), "", ""],
            [Paragraph("<b>Date</b>", normal_style), Paragraph(":", normal_style), Paragraph(f"{tanggal}", normal_style)],
            [Paragraph("<b>No.</b>", normal_style), Paragraph(":", normal_style), Paragraph(f"{no_inv}", normal_style)],
            [Paragraph("<b>Term Payment</b>", normal_style), Paragraph(":", normal_style), Paragraph(f"{term_payment}", normal_style)],
            [Paragraph("<b>Loco To</b>", normal_style), Paragraph(":", normal_style), Paragraph(f"{po_loco_to}", normal_style)],
            [Paragraph("<b>Delivery</b>", normal_style), Paragraph(":", normal_style), Paragraph(f"{po_delivery}", normal_style)],
            [Paragraph("<b>Validity</b>", normal_style), Paragraph(":", normal_style), Paragraph(f"{validity_term}", normal_style)],
        ]
    else:
        right_header_data = [
            [Paragraph(judul_formatted, style_judul_tengah), "", ""],
            [Paragraph("<b>Date</b>", normal_style), Paragraph(":", normal_style), Paragraph(f"{tanggal}", normal_style)],
            [Paragraph("<b>No.</b>", normal_style), Paragraph(":", normal_style), Paragraph(f"{no_inv}", normal_style)],
        ]
        if no_sj and no_sj != "(Kosong / Tanpa Referensi)":
            right_header_data.append([Paragraph("<b>No. Surat Jalan</b>", normal_style), Paragraph(":", normal_style), Paragraph(f"{no_sj}", normal_style)])
        if no_po and no_po != "(Kosong / Tanpa Referensi)":
            right_header_data.append([Paragraph("<b>No. PO</b>", normal_style), Paragraph(":", normal_style), Paragraph(f"{no_po}", normal_style)])
        if no_quo and no_quo != "(Kosong / Tanpa Referensi)":
            right_header_data.append([Paragraph("<b>No. Quo</b>", normal_style), Paragraph(":", normal_style), Paragraph(f"{no_quo}", normal_style)])

    right_table = Table(right_header_data, colWidths=[85, 10, 115])
    right_table.setStyle(
        TableStyle([
            ("SPAN", (0, 0), (2, 0)),
            ("ALIGN", (0, 0), (2, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ])
    )

    header_table = Table([[left_header, right_table]], colWidths=[330, 210])
    header_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ])
    )
    story.append(header_table)
    story.append(Spacer(1, 6))
    story.append(
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#9b2c2c"), spaceBefore=2, spaceAfter=8)
    )

    if tampilkan_customer:
        cust_style = ParagraphStyle("CustCompact", parent=normal_style, fontSize=8.5, leading=11)
        left_cust_data = [
            [Paragraph("<b>Customer</b>", cust_style), Paragraph(":", cust_style), Paragraph(f"{klien}", cust_style)],
            [Paragraph("<b>Attn</b>", cust_style), Paragraph(":", cust_style), Paragraph(f"{division}", cust_style)],
            [Paragraph("<b>Phone</b>", cust_style), Paragraph(":", cust_style), Paragraph(f"{telp}", cust_style)],
            [Paragraph("<b>Subject</b>", cust_style), Paragraph(":", cust_style), Paragraph(f"{subject}", cust_style)],
        ]
        left_cust_table = Table(left_cust_data, colWidths=[55, 10, 215])
        left_cust_table.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ])
        )

        right_cust_data = [
            [Paragraph("<b>PIC</b>", cust_style), Paragraph(":", cust_style), Paragraph(f"{pic}", cust_style)],
            [Paragraph("<b>Division</b>", cust_style), Paragraph(":", cust_style), Paragraph(f"{division}", cust_style)],
            [Paragraph("<b>Email</b>", cust_style), Paragraph(":", cust_style), Paragraph(f"{email if email else '-'}", cust_style)],
            [Paragraph("", cust_style), Paragraph("", cust_style), Paragraph("", cust_style)],
        ]
        right_cust_table = Table(right_cust_data, colWidths=[50, 10, 200])
        right_cust_table.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ])
        )

        cust_wrapper_table = Table([[left_cust_table, right_cust_table]], colWidths=[280, 260])
        cust_wrapper_table.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ])
        )
        story.append(cust_wrapper_table)
        story.append(Spacer(1, 8))

    if jenis_dok == "Tanda Terima":
        invoice_no = tanda_terima_invoice_no or no_inv or "-"
        invoice_date = tanda_terima_invoice_date or tanggal or "-"
        amount = float(tanda_terima_amount if tanda_terima_amount is not None else grand_total or 0)

        tt_header_style = ParagraphStyle("TTHeader", parent=normal_style, fontSize=8, leading=10, fontName="Helvetica-Bold", textColor=colors.whitesmoke, alignment=1)
        tt_cell_style = ParagraphStyle("TTCell", parent=normal_style, fontSize=8, leading=10, alignment=0)
        tt_center_style = ParagraphStyle("TTCenter", parent=normal_style, fontSize=8, leading=10, alignment=1)
        tt_right_style = ParagraphStyle("TTRight", parent=normal_style, fontSize=8, leading=10, alignment=2)
        tt_total_style = ParagraphStyle("TTTotal", parent=normal_style, fontSize=8, leading=10, fontName="Helvetica-Bold", alignment=2)

        tt_data = [
            [Paragraph("No.", tt_header_style), Paragraph("FAKTUR / INVOICE NO.", tt_header_style), Paragraph("TANGGAL", tt_header_style), Paragraph("JUMLAH (RP)", tt_header_style)],
            [Paragraph("1", tt_center_style), Paragraph(str(invoice_no), tt_cell_style), Paragraph(str(invoice_date), tt_center_style), Paragraph(f"Rp {amount:,.0f}", tt_right_style)],
            [Paragraph("", tt_cell_style), Paragraph("", tt_cell_style), Paragraph("<b>TOTAL</b>", tt_total_style), Paragraph(f"<b>Rp {amount:,.0f}</b>", tt_total_style)],
        ]

        tt_table = Table(tt_data, colWidths=[30, 200, 110, 170])
        tt_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#9b2c2c")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#8a8a8a")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("SPAN", (0, 2), (1, 2)),
                ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#fff5f5")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ])
        )
        story.append(tt_table)
        story.append(Spacer(1, 18))
        story.append(Paragraph("Telah diterima dokumen / pembayaran dengan baik dan sah.", ParagraphStyle("TTNote", parent=normal_style, fontSize=8.5, leading=12, textColor=colors.HexColor("#2d3748"))))
        story.append(Spacer(1, 22))

        tt_sign = Table(
            [
                [Paragraph("<b>Hormat Kami,</b>", ParagraphStyle("TTHormat", parent=normal_style, fontSize=8.5, alignment=0)), Paragraph("<b>Diterima Oleh,</b>", ParagraphStyle("TTDiterima", parent=normal_style, fontSize=8.5, alignment=2))],
                [Spacer(1, 45), Spacer(1, 45)],
                [Paragraph(f"<b>{profil_pdf.get('direktur', 'Hidayat')}</b><br/>Sales Marketing", ParagraphStyle("TTNama", parent=normal_style, fontSize=8.5, leading=11, alignment=0)), Paragraph(f"( __________________________ )<br/><b>{penerima_nama or 'Customer / Penerima'}</b>", ParagraphStyle("TTPenerima", parent=normal_style, fontSize=8.5, leading=11, alignment=2))],
            ],
            colWidths=[270, 270],
        )
        tt_sign.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        story.append(tt_sign)

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    if jenis_dok == "Purchase Order":
        kolom_header = ["No", "Nama Barang", "QTY", "Satuan", "KETERANGAN", "Total Price"]
        lebar_kol = [28, 245, 42, 55, 95, 70]
    elif jenis_dok in ["Invoice", "Quotation / Penawaran"]:
        kolom_header = ["No", "Description", "QTY", "Satuan", "Unit Price", "Total Price"]
        lebar_kol = [28, 245, 42, 55, 95, 70]

    header_table_paragraphs = [
        Paragraph(
            f"<b>{col}</b>",
            ParagraphStyle(f"Hdr_{idx}", parent=normal_style, fontSize=8, leading=10, fontName="Helvetica-Bold", textColor=colors.whitesmoke, alignment=1 if idx > 0 else 0),
        )
        for idx, col in enumerate(kolom_header)
    ]
    table_data = [header_table_paragraphs]

    for idx, item in enumerate(items, start=1):
        ket_raw = item.get("ket", "")
        sub_lines = [s.strip() for s in ket_raw.split("\n") if s.strip()]
        desc_html = f"<b>{item['nama']}</b>"
        for sub in sub_lines:
            desc_html += f"<br/>{sub}"

        if jenis_dok == "Surat Jalan":
            table_data.append([
                Paragraph(str(idx), table_cell_style),
                Paragraph(desc_html, table_desc_quotation),
                Paragraph(str(item["qty"]), table_cell_style),
                Paragraph("Unit", table_cell_style),
                Paragraph("-", table_cell_style),
            ])
        else:
            if tampilkan_harga:
                if jenis_dok == "Purchase Order":
                    po_desc_style = ParagraphStyle("PODescCell", parent=table_desc_quotation, fontSize=7.5, leading=9)
                    po_cell_style = ParagraphStyle("POCell", parent=table_cell_style, fontSize=7.5, leading=9)
                    table_data.append([
                        Paragraph(str(idx), po_cell_style),
                        Paragraph(desc_html, po_desc_style),
                        Paragraph(str(item["qty"]), po_cell_style),
                        Paragraph("Unit", po_cell_style),
                        Paragraph(f"Rp {item['harga']:,.0f}", po_cell_style),
                        Paragraph(f"Rp {item['total']:,.0f}", po_cell_style),
                    ])
                else:
                    inv_cell_style = ParagraphStyle("InvCell", parent=table_cell_style, fontSize=7.5, leading=9)
                    inv_desc_style = ParagraphStyle("InvDescCell", parent=table_desc_quotation, fontSize=7.5, leading=9)
                    table_data.append([
                        Paragraph(str(idx), inv_cell_style),
                        Paragraph(desc_html, inv_desc_style),
                        Paragraph(str(item["qty"]), inv_cell_style),
                        Paragraph("Unit", inv_cell_style),
                        Paragraph(f"Rp {item['harga']:,.0f}", inv_cell_style),
                        Paragraph(f"Rp {item['total']:,.0f}", inv_cell_style),
                    ])
            else:
                table_data.append([
                    Paragraph(str(idx), table_cell_style),
                    Paragraph(desc_html, table_desc_quotation),
                    Paragraph(str(item["qty"]), table_cell_style),
                    Paragraph("Unit", table_cell_style),
                    Paragraph("-", table_cell_style),
                    Paragraph("-", table_cell_style),
                ])

    if jenis_dok != "Surat Jalan" and tampilkan_harga:
        style_sub_label = ParagraphStyle("SubLbl", parent=normal_style, fontSize=8, leading=10, fontName="Helvetica-Bold", alignment=2)
        style_sub_val = ParagraphStyle("SubVal", parent=normal_style, fontSize=8, leading=10, fontName="Helvetica-Bold", alignment=2)

        table_data.append([Paragraph("SUB TOTAL", style_sub_label), Paragraph("", table_cell_style), Paragraph("", table_cell_style), Paragraph("", table_cell_style), Paragraph("", table_cell_style), Paragraph(f"Rp {subtotal:,.0f}", style_sub_val)])
        table_data.append([Paragraph("DISCOUNT", style_sub_label), Paragraph("", table_cell_style), Paragraph("", table_cell_style), Paragraph("", table_cell_style), Paragraph("", table_cell_style), Paragraph(f"Rp {discount:,.0f}", style_sub_val)])
        table_data.append([Paragraph("PPH 23", style_sub_label), Paragraph("", table_cell_style), Paragraph("", table_cell_style), Paragraph("", table_cell_style), Paragraph("", table_cell_style), Paragraph(f"Rp {pph23:,.0f}", style_sub_val)])
        table_data.append([Paragraph("DPP LAINNYA", style_sub_label), Paragraph("", table_cell_style), Paragraph("", table_cell_style), Paragraph("", table_cell_style), Paragraph("", table_cell_style), Paragraph(f"Rp {dpp_lainnya:,.0f}", style_sub_val)])
        table_data.append([Paragraph(label_ppn, style_sub_label), Paragraph("", table_cell_style), Paragraph("", table_cell_style), Paragraph("", table_cell_style), Paragraph("", table_cell_style), Paragraph(f"Rp {ppn:,.0f}", style_sub_val)])
        table_data.append([Paragraph("GRAND TOTAL", style_sub_label), Paragraph("", table_cell_style), Paragraph("", table_cell_style), Paragraph("", table_cell_style), Paragraph("", table_cell_style), Paragraph(f"Rp {grand_total:,.0f}", style_sub_val)])

        item_table = Table(table_data, colWidths=lebar_kol)
        item_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#9b2c2c")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("GRID", (0, 0), (-1, -7), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("SPAN", (0, -6), (4, -6)),
                ("SPAN", (0, -5), (4, -5)),
                ("SPAN", (0, -4), (4, -4)),
                ("SPAN", (0, -3), (4, -3)),
                ("SPAN", (0, -2), (4, -2)),
                ("SPAN", (0, -1), (4, -1)),
                ("GRID", (0, -6), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fff5f5")),
            ])
        )
    else:
        item_table = Table(table_data, colWidths=lebar_kol)
        item_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#9b2c2c")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )

    story.append(item_table)
    story.append(Spacer(1, 10))

    if jenis_dok in ["Invoice", "Quotation / Penawaran"]:
        terbilang_teks = f"<b>Terbilang : <i># {format_terbilang(grand_total)} #</i></b>"
        story.append(Paragraph(terbilang_teks, ParagraphStyle("TerbilangInv", parent=normal_style, fontSize=9, leading=13, textColor=colors.HexColor("#1a202c"))))
        story.append(Spacer(1, 6))

    if jenis_dok == "Quotation / Penawaran":
        tc_data = [
            [Paragraph("<u><b>Terms & Condition</b></u>", ParagraphStyle("TCTitle", parent=normal_style, fontSize=8, leading=11, fontName="Helvetica-Bold", alignment=0)), Paragraph("", normal_style)],
            [Paragraph("Term Payment", ParagraphStyle("TC1", parent=normal_style, fontSize=8, leading=11, alignment=0)), Paragraph(f": {term_payment}", ParagraphStyle("TC2", parent=normal_style, fontSize=8, leading=11, alignment=0))],
            [Paragraph("Validity", ParagraphStyle("TC3", parent=normal_style, fontSize=8, leading=11, alignment=0)), Paragraph(f": {validity_term}", ParagraphStyle("TC4", parent=normal_style, fontSize=8, leading=11, alignment=0))],
            [Paragraph("Note", ParagraphStyle("TC5", parent=normal_style, fontSize=8, leading=11, alignment=0)), Paragraph(f": {note_text}", ParagraphStyle("TC6", parent=normal_style, fontSize=8, leading=11, alignment=0))],
            [Paragraph("", ParagraphStyle("TC7", parent=normal_style, fontSize=8, leading=11, alignment=0)), Paragraph(f"Please send PO or sign Confirmation to <b>{email_target}</b>", ParagraphStyle("TC8", parent=normal_style, fontSize=8, leading=11, alignment=0))],
        ]
        tc_table = Table(tc_data, colWidths=[75, 380])
        tc_table.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("SPAN", (1, 4), (1, 4)),
            ])
        )
        story.append(tc_table)
        story.append(Spacer(1, 10))

    if jenis_dok == "Purchase Order":
        po_note_style = ParagraphStyle("PONote", parent=normal_style, fontSize=7.7, leading=10.5, textColor=colors.HexColor("#2d3748"))
        po_notes_text = po_notes or "<b>Catatan &amp; Ketentuan Purchase Order:</b><br/>1. Harap konfirmasi jika PO sudah diterima...<br/>2. Jumlah tagihan invoice harus sesuai..."
        if po_notes:
            po_notes_text = str(po_notes).replace("\n", "<br/>")
        story.append(Spacer(1, 7))
        story.append(Paragraph(po_notes_text, po_note_style))
        story.append(Spacer(1, 12))

        po_box_style = ParagraphStyle("POBox", parent=normal_style, fontSize=7.5, leading=9, alignment=0)
        po_center_style = ParagraphStyle("POCenter", parent=normal_style, fontSize=7.5, leading=9, alignment=1)
        po_prepared = po_prepared_by or "Procurement"
        po_authorized = po_authorized_by or profil_pdf.get("direktur", "Direktur")

        approval_table = Table(
            [
                [Paragraph("<b>Prepared</b>", po_box_style), Paragraph("<b>Authorized</b>", po_box_style), Paragraph("<b>Supplier/Vendor Confirmation</b>", po_box_style)],
                [Paragraph("Date", po_box_style), Paragraph("Date", po_box_style), Paragraph("Date:", po_box_style)],
                [Spacer(1, 45), Spacer(1, 45), Paragraph("", po_box_style)],
                [Paragraph(f"<b>{po_prepared}</b>", po_center_style), Paragraph(f"<b>{po_authorized}</b>", po_center_style), Paragraph("Nama: ....................................", po_box_style)],
            ],
            colWidths=[115, 115, 250],
            rowHeights=[18, 18, 55, 22],
        )
        approval_table.setStyle(TableStyle([
            ("GRID", (0, 0), (1, 3), 0.7, colors.HexColor("#6b7280")),
            ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#edf2f7")),
            ("BACKGROUND", (0, 3), (1, 3), colors.HexColor("#edf2f7")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(approval_table)
    elif jenis_dok == "Surat Jalan":
        story.append(Paragraph(catatan_footer, ParagraphStyle("FootNoteSJ", parent=normal_style, fontSize=8, leading=11, textColor=colors.HexColor("#2d3748"))))
        story.append(Spacer(1, 15))

        sign_sj_data = [
            [Paragraph("<b>Penerima,</b>", ParagraphStyle("S1", parent=normal_style, fontSize=8, alignment=1)), Paragraph("<b>Expedisi / Supir,</b>", ParagraphStyle("S2", parent=normal_style, fontSize=8, alignment=1)), Paragraph("<b>Security,</b>", ParagraphStyle("S3", parent=normal_style, fontSize=8, alignment=1)), Paragraph("<b>Hormat Kami,</b>", ParagraphStyle("S4", parent=normal_style, fontSize=8, alignment=1))],
            [Spacer(1, 35), Spacer(1, 35), Spacer(1, 35), Spacer(1, 35)],
            [Paragraph("( . . . . . . . . . . . )", ParagraphStyle("S5", parent=normal_style, fontSize=8, alignment=1)), Paragraph("( . . . . . . . . . . . )", ParagraphStyle("S6", parent=normal_style, fontSize=8, alignment=1)), Paragraph("( . . . . . . . . . . . )", ParagraphStyle("S7", parent=normal_style, fontSize=8, alignment=1)), Paragraph(f"<b>{profil_pdf.get('direktur', 'Hidayat')}</b>", ParagraphStyle("S8", parent=normal_style, fontSize=8, fontName="Helvetica-Bold", alignment=1))],
        ]
        sign_sj_table = Table(sign_sj_data, colWidths=[135, 135, 135, 135])
        sign_sj_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        story.append(sign_sj_table)
    else:
        catatan_pembayaran_obj = Paragraph(catatan_footer, ParagraphStyle("FootNote", parent=normal_style, fontSize=8, leading=11, textColor=colors.HexColor("#2d3748")))
        ttd_content = [
            Paragraph("<b>Hormat kami,</b>", ParagraphStyle("Hormat", parent=normal_style, fontSize=8, leading=10, alignment=1)),
            Spacer(1, 35),
            Paragraph(f"<b>{profil_pdf.get('direktur', 'Hidayat')}</b>", ParagraphStyle("NamaHidayat", parent=normal_style, fontSize=8, leading=10, fontName="Helvetica-Bold", alignment=1)),
        ]
        sign_table = Table([[catatan_pembayaran_obj, ttd_content]], colWidths=[320, 220])
        sign_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        story.append(Spacer(1, 5))
        story.append(sign_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# --- SIDEBAR & MENU UTAMA SETELAH LOGIN ---
logo_path = "logo_nagami.png"
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, width=160)

st.sidebar.success(f"Masuk sebagai: **{st.session_state.username.upper()}**\nRole: *{st.session_state.user_role}*")
if st.sidebar.button("🚪 Logout (Keluar)"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.user_role = ""
    st.rerun()

st.sidebar.title("📌 Menu Utama NAGAMI")

menu_options = [
    "Dashboard Analitik",
    "Buat Dokumen",
    "Klien",
    "Supplier",
    "Stok & Barang",
    "Pembelian",
    "Rekap & Piutang",
    "Laporan Pajak",
    "Backup/Restore",
    "Pengaturan Perusahaan & Logo",
    "Konfigurasi SMTP (Email)",
]

if st.session_state.user_role == "Staff / Marketing":
    allowed_menus = ["Dashboard Analitik", "Buat Dokumen", "Klien", "Stok & Barang", "Rekap & Piutang"]
    menu = st.sidebar.selectbox("Pilih Menu", allowed_menus)
else:
    menu = st.sidebar.selectbox("Pilih Menu", menu_options)


# --- 0. MENU: DASHBOARD ANALITIK ---
if menu == "Dashboard Analitik":
    st.subheader("📊 Dashboard Analitik Keuangan & Operasional")
    invoice_records = [inv for inv in data_invoice_history if _infer_jenis_dokumen(inv) == "Invoice"]

    total_penjualan = sum(float(inv.get("grand_total", 0) or 0) for inv in invoice_records)
    total_piutang = sum(float(inv.get("grand_total", 0) or 0) for inv in invoice_records if inv.get("status", "Belum Lunas (Piutang)") == "Belum Lunas (Piutang)")
    total_pembelian = sum(float(p.get("total", 0) or 0) for p in data_pembelian)
    laba_bersih = (total_penjualan - total_piutang) - total_pembelian

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Penjualan", f"Rp {total_penjualan:,.0f}")
    c2.metric("Total Piutang Aktif", f"Rp {total_piutang:,.0f}")
    c3.metric("Total Pengeluaran", f"Rp {total_pembelian:,.0f}")
    c4.metric("Estimasi Laba Cair", f"Rp {laba_bersih:,.0f}")

    st.markdown("---")
    if invoice_records:
        df_inv = pd.DataFrame(invoice_records)
        if "tanggal" in df_inv.columns and "grand_total" in df_inv.columns:
            st.write("### 📈 Tren Omset Penjualan Berdasarkan Tanggal")
            chart_df = df_inv[["tanggal", "grand_total"]].copy()
            chart_df["grand_total"] = chart_df["grand_total"].astype(float)
            st.line_chart(chart_df.set_index("tanggal"))
    else:
        st.info("Belum ada data penjualan untuk ditampilkan grafiknya.")


# --- 1. MENU: BUAT DOKUMEN ---
elif menu == "Buat Dokumen":
    col_title_txt, col_title_img = st.columns([0.85, 0.15])
    with col_title_txt:
        st.subheader("📝 Buat Dokumen & Cetak PDF Otomatis")
    with col_title_img:
        if os.path.exists(logo_path):
            st.image(logo_path, width=70)

    jenis_dok = st.selectbox(
        "Jenis Dokumen",
        ["Invoice", "Quotation / Penawaran", "Surat Jalan", "Purchase Order", "Tanda Terima"],
    )

    list_existing_no = [inv.get("no_dokumen") or inv.get("no_inv") for inv in data_invoice_history]
    options_ref = ["(Kosong / Tanpa Referensi)"] + list_existing_no

    col1, col2 = st.columns(2)
    with col1:
        tgl_dok = st.text_input("Tanggal (dd-mm-yyyy)", value=datetime.now().strftime("%d-%m-%Y"))
        nomor_session_key = f"no_dokumen_{jenis_dok}"
        if nomor_session_key not in st.session_state:
            st.session_state[nomor_session_key] = generate_auto_no_dokumen(jenis_dok)

        no_dok = st.text_input("No. Dokumen", key=nomor_session_key)
        names_klien = [k["nama"] for k in data_klien] if data_klien else []
        pilih_klien = st.selectbox("Pilih Klien Master", names_klien if names_klien else ["(Belum ada klien)"])
        pic_text = st.text_input("PIC / Attn", value="Bpk. Pimpinan")
        division_text = st.text_input("Division", value="PURCHASING")
        
        no_sj_ref = st.selectbox("No. Surat Jalan / Ref", options=options_ref)
        no_po_ref = st.selectbox("No. PO", options=options_ref)
        no_quo_ref = st.selectbox("No. Quo", options=options_ref)

        tanda_terima_invoice_no = None
        tanda_terima_invoice_date = None
        tanda_terima_amount = 0.0
        penerima_nama = "Customer / Penerima"

        if jenis_dok == "Tanda Terima":
            invoice_options = [
                inv.get("no_dokumen") or inv.get("no_inv")
                for inv in data_invoice_history
                if _infer_jenis_dokumen(inv) == "Invoice" and (inv.get("no_dokumen") or inv.get("no_inv"))
            ]
            invoice_options = list(dict.fromkeys(invoice_options))
            invoice_options = ["(Pilih Invoice)"] + invoice_options
            tanda_terima_invoice_no = st.selectbox("No. Invoice yang Diterima", invoice_options)

            selected_tt = None
            if tanda_terima_invoice_no != "(Pilih Invoice)":
                selected_tt = next(
                    (inv for inv in data_invoice_history if (inv.get("no_dokumen") or inv.get("no_inv")) == tanda_terima_invoice_no and _infer_jenis_dokumen(inv) == "Invoice"),
                    None,
                )

            if selected_tt:
                if not names_klien or selected_tt.get("klien") in names_klien:
                    pilih_klien = selected_tt.get("klien", pilih_klien)
                tanda_terima_invoice_date = selected_tt.get("tanggal", tgl_dok)
                tanda_terima_amount = float(selected_tt.get("grand_total", 0) or 0)
            else:
                tanda_terima_invoice_date = tgl_dok

            tanda_terima_invoice_date = st.text_input("Tanggal Invoice", value=tanda_terima_invoice_date or tgl_dok)
            tanda_terima_amount = st.number_input("Jumlah Diterima (Rp)", min_value=0.0, value=float(tanda_terima_amount), step=1000.0)
            penerima_nama = st.text_input("Nama Penerima", value="Customer / Penerima")

    with col2:
        pilihan_ppn = st.selectbox("Pengaturan PPN", ["PPN 11%", "Tanpa PPN (0%)"])
        diskon_global = st.number_input("Diskon Global (Rp)", min_value=0.0, value=0.0, step=1000.0)
        pph23 = st.number_input("PPH 23 (Rp)", min_value=0.0, value=0.0, step=1000.0)
        dpp_lainnya = st.number_input("DPP Lainnya (Rp)", min_value=0.0, value=0.0, step=1000.0)
        status_byr = st.selectbox("Status Pembayaran", ["Belum Lunas (Piutang)", "Lunas"])

    term_payment_val = "30 day after invoice"
    validity_val = "1 week"
    note_val = "Prices are not fixed depending on the materials/goods available"
    email_val = "marketing@nagami.co.id"

    po_loco_to_val = "PT. Nata Gatra Mitra"
    po_delivery_val = "Indent 2-3 week"
    po_prepared_val = "Procurement"
    po_authorized_val = "Direktur"
    po_notes_val = None

    if jenis_dok == "Quotation / Penawaran":
        with st.expander("⚙️ Pengaturan Terms & Condition Quotation"):
            term_payment_val = st.text_input("Term Payment", value="30 day after invoice")
            validity_val = st.text_input("Validity", value="1 week")
            note_val = st.text_input("Note", value="Prices are not fixed depending on the materials/goods available")
            email_val = st.text_input("Email Tujuan PO / Konfirmasi", value="marketing@nagami.co.id")

    if jenis_dok == "Purchase Order":
        with st.expander("⚙️ Pengaturan Purchase Order", expanded=True):
            term_payment_val = st.text_input("Term Payment", value="30 day after invoice")
            po_loco_to_val = st.text_input("Loco To", value="PT. Nata Gatra Mitra")
            po_delivery_val = st.text_input("Delivery", value="Indent 2-3 week")
            validity_val = st.text_input("Validity", value="1 week")
            po_prepared_val = st.text_input("Prepared By", value="Procurement")
            po_authorized_val = st.text_input("Authorized By", value="Direktur")
            po_notes_val = st.text_area("Catatan & Ketentuan PO", value="Catatan & Ketentuan Purchase Order:\n1. Harap konfirmasi jika PO sudah diterima...", height=130)

    st.markdown("---")

    if jenis_dok != "Tanda Terima":
        st.write("### Daftar Item Barang / Jasa ke Dokumen")

    if "cart_items" not in st.session_state:
        st.session_state.cart_items = []
    
    if jenis_dok != "Tanda Terima":
        if no_po_ref and no_po_ref != "(Kosong / Tanpa Referensi)":
            if st.button("🔄 Tarik Item Otomatis dari No. PO Terpilih"):
                found_po = False
                for inv in data_invoice_history:
                    if (inv.get("no_dokumen") or inv.get("no_inv")) == no_po_ref and _infer_jenis_dokumen(inv) == "Purchase Order":
                        st.session_state.cart_items = list(inv.get("items", []))
                        if "klien" in inv and inv["klien"] in names_klien:
                            pilih_klien = inv["klien"]
                        found_po = True
                        break
                if found_po:
                    st.success(f"Berhasil menarik item dari PO {no_po_ref}!")
                    st.rerun()
                else:
                    st.warning("Data item untuk No. PO tersebut tidak ditemukan di riwayat.")

        col_i1, col_i2, col_i3, col_i4 = st.columns([2, 1, 1, 1])
        with col_i1:
            names_barang = [b["nama"] for b in data_barang] if data_barang else []
            pilih_brg = st.selectbox("Pilih Barang", names_barang if names_barang else ["(Belum ada barang)"])
        with col_i2:
            item_qty = st.number_input("Qty", min_value=1, value=1)
        with col_i3:
            default_harga = 0.0
            for b in data_barang:
                if b["nama"] == pilih_brg:
                    default_harga = b["harga"]
                    break
            item_harga = st.number_input("Harga Satuan (Rp)", min_value=0.0, value=default_harga, step=1000.0)
        with col_i4:
            item_diskon = st.number_input("Diskon Item (Rp)", min_value=0.0, value=0.0, step=1000.0)

        item_ket = st.text_area("Detail / Sub-Pekerjaan (Tekan Enter untuk baris baru)", value="")

        if st.button("➕ Tambahkan Item Manual"):
            if pilih_brg and pilih_brg != "(Belum ada barang)":
                total_item = max(0.0, (item_qty * item_harga) - item_diskon)
                st.session_state.cart_items.append({
                    "nama": pilih_brg, "qty": item_qty, "harga": item_harga,
                    "diskon": item_diskon, "ket": item_ket, "total": total_item,
                })
                st.success(f"Item '{pilih_brg}' berhasil ditambahkan!")
                st.rerun()
            else:
                st.error("Pilih barang yang valid terlebih dahulu!")

        if st.session_state.cart_items:
            st.write("#### Daftar Item Saat Ini:")
            for idx, item in enumerate(st.session_state.cart_items, 1):
                st.write(f"{idx}. **{item['nama']}** | Qty: {item['qty']} | Harga: Rp {item['harga']:,.0f} | Total: Rp {item['total']:,.0f}")

            if st.button("🗑️ Kosongkan Daftar Item"):
                st.session_state.cart_items = []
                st.rerun()
    else:
        st.info("Format Bukti Tanda Terima menggunakan No. Invoice dan jumlah yang diterima.")

    st.markdown("---")
    if st.button("💾 Simpan Dokumen & Buat PDF", type="primary"):
        if jenis_dok == "Tanda Terima":
            valid_tt = bool(no_dok) and bool(names_klien) and tanda_terima_invoice_no and tanda_terima_invoice_no != "(Pilih Invoice)" and float(tanda_terima_amount or 0) > 0
            if not valid_tt:
                st.error("Pilih Invoice dan pastikan jumlah diterima > Rp 0.")
                st.stop()
        elif not no_dok or not names_klien or not st.session_state.cart_items:
            st.error("Lengkapi No Dokumen, Klien, dan minimal 1 item barang!")
            st.stop()

        if jenis_dok == "Tanda Terima":
            subtotal_all = float(tanda_terima_amount)
            ppn_val = 0.0
            label_ppn_str = "Tanpa PPN"
            grand_total = float(tanda_terima_amount)
            save_items = []
        else:
            subtotal_all = sum(i["total"] for i in st.session_state.cart_items)
            ppn_val = (subtotal_all - diskon_global) * 0.11 if "PPN 11%" in pilihan_ppn else 0.0
            label_ppn_str = "*Belum termasuk PPN 11%" if "PPN 11%" in pilihan_ppn else "*Tanpa PPN (0%)"
            grand_total = (subtotal_all - diskon_global) + ppn_val - pph23 + dpp_lainnya
            save_items = list(st.session_state.cart_items)

        no_dok = no_dok.strip()
        if nomor_dokumen_sudah_ada(no_dok):
            st.error(f"Nomor dokumen {no_dok} sudah digunakan.")
            st.stop()

        if jenis_dok == "Surat Jalan":
            stock_errors, _ = validate_stock_out(save_items)
            if stock_errors:
                st.error("Stok tidak mencukupi untuk Surat Jalan ini:")
                for err in stock_errors:
                    st.warning(err)
                st.stop()

        new_doc = {
            "jenis_dokumen": jenis_dok,
            "no_dokumen": no_dok,
            "no_inv": no_dok,
            "tanggal": tgl_dok,
            "klien": pilih_klien,
            "grand_total": float(grand_total),
            "status": status_byr,
            "items": save_items,
            "subtotal": float(subtotal_all),
            "discount": float(diskon_global if jenis_dok != "Tanda Terima" else 0),
            "pph23": float(pph23 if jenis_dok != "Tanda Terima" else 0),
            "dpp_lainnya": float(dpp_lainnya if jenis_dok != "Tanda Terima" else 0),
            "ppn": float(ppn_val),
            "pilihan_ppn": pilihan_ppn if jenis_dok != "Tanda Terima" else "Tanpa PPN (0%)",
            "label_ppn": label_ppn_str,
            "no_sj": no_sj_ref,
            "no_po": no_po_ref,
            "no_quo": no_quo_ref,
            "pic": pic_text,
            "division": division_text,
            "subject": "PENGADAAN BARANG / JASA",
            "term_payment": term_payment_val,
            "validity_term": validity_val,
            "note_text": note_val,
            "email_target": email_val,
            "tanda_terima_invoice_no": tanda_terima_invoice_no,
            "tanda_terima_invoice_date": tanda_terima_invoice_date,
            "tanda_terima_amount": float(tanda_terima_amount or 0),
            "penerima_nama": penerima_nama,
            "po_loco_to": po_loco_to_val,
            "po_delivery": po_delivery_val,
            "po_prepared_by": po_prepared_val,
            "po_authorized_by": po_authorized_val,
            "po_notes": po_notes_val,
        }

        data_invoice_history.append(new_doc)
        save_data(FILE_INVOICE, data_invoice_history)

        if jenis_dok == "Surat Jalan":
            ok_stock, stock_errors = apply_stock_out_for_document(save_items, no_dok, tgl_dok)

        reserve_no_dokumen(no_dok, jenis_dok)
        log_activity("BUAT_DOKUMEN", f"Membuat {jenis_dok} nomor {no_dok} untuk klien {pilih_klien}")

        pdf_data = buat_pdf_bytes(
            jenis_dok=jenis_dok, no_inv=no_dok, no_sj=no_sj_ref, tanggal=tgl_dok,
            no_po=no_po_ref, no_quo=no_quo_ref, klien=pilih_klien, telp="-", email="-",
            pic=pic_text, division=division_text, subject="PENGADAAN BARANG / JASA",
            term_payment=term_payment_val, validity_term=validity_val, note_text=note_val,
            email_target=email_val, items=save_items, subtotal=subtotal_all,
            discount=float(diskon_global if jenis_dok != "Tanda Terima" else 0),
            pph23=float(pph23 if jenis_dok != "Tanda Terima" else 0),
            dpp_lainnya=float(dpp_lainnya if jenis_dok != "Tanda Terima" else 0),
            ppn=ppn_val, label_ppn=label_ppn_str, grand_total=grand_total,
            tanda_terima_invoice_no=tanda_terima_invoice_no, tanda_terima_invoice_date=tanda_terima_invoice_date,
            tanda_terima_amount=tanda_terima_amount, penerima_nama=penerima_nama,
            po_loco_to=po_loco_to_val, po_delivery=po_delivery_val, po_prepared_by=po_prepared_val,
            po_authorized_by=po_authorized_val, po_notes=po_notes_val,
        )

        st.session_state["pdf_terakhir_data"] = pdf_data
        st.session_state["pdf_terakhir_nama"] = f"{jenis_dok.replace(' ', '_')}_{no_dok.replace('/', '_')}.pdf"
        st.session_state["pdf_terakhir_jenis"] = jenis_dok
        st.session_state["pdf_terakhir_no"] = no_dok

        if jenis_dok != "Tanda Terima":
            st.session_state.cart_items = []
        st.session_state.pop(nomor_session_key, None)

        st.success(f"Dokumen {jenis_dok} nomor {no_dok} berhasil disimpan!")

    if st.session_state.get("pdf_terakhir_data"):
        st.markdown("### 📥 Download & Kirim PDF Terakhir")
        st.download_button(
            label=f"📥 DOWNLOAD PDF {st.session_state.get('pdf_terakhir_jenis')} {st.session_state.get('pdf_terakhir_no')}",
            data=st.session_state["pdf_terakhir_data"],
            file_name=st.session_state.get("pdf_terakhir_nama", "dokumen.pdf"),
            mime="application/pdf",
        )

        with st.expander("📧 Kirim Dokumen via Email Langsung"):
            email_tujuan = st.text_input("Email Tujuan", value="client@example.com")
            if st.button("📤 Kirim Email Sekarang"):
                subjek_email = f"Dokumen {st.session_state.get('pdf_terakhir_jenis')} - PT Nata Gatra Mitra"
                pesan_email = f"Yth. Bapak/Ibu,\n\nBerikut kami lampirkan dokumen {st.session_state.get('pdf_terakhir_jenis')} nomor {st.session_state.get('pdf_terakhir_no')} dari PT Nata Gatra Mitra.\n\nTerima kasih atas kerjasamanya."
                success, msg = kirim_email_pdf(
                    email_tujuan, subjek_email, pesan_email,
                    st.session_state["pdf_terakhir_data"], st.session_state["pdf_terakhir_nama"]
                )
                if success:
                    st.success(msg)
                else:
                    st.error(msg)


# --- 2. MENU: KLIEN ---
elif menu == "Klien":
    st.subheader("👥 Manajemen Master Klien")
    with st.form("form_klien"):
        nama_k = st.text_input("Nama Perusahaan / Klien")
        alamat_k = st.text_area("Alamat Lengkap")
        telp_k = st.text_input("No. Telepon / WhatsApp")
        email_k = st.text_input("Email")
        npwp_k = st.text_input("NPWP")
        submit_k = st.form_submit_button("Simpan Klien Baru")

        if submit_k:
            if nama_k and alamat_k:
                data_klien.append({"nama": nama_k, "alamat": alamat_k, "telp": telp_k, "email": email_k, "npwp": npwp_k})
                save_data(FILE_KLIEN, data_klien)
                log_activity("TAMBAH_KLIEN", f"Menambahkan klien baru: {nama_k}")
                st.success(f"Klien '{nama_k}' berhasil disimpan!")
                st.rerun()
            else:
                st.error("Nama dan Alamat wajib diisi!")

    st.write("### Daftar Klien Tersimpan")
    if data_klien:
        st.table(data_klien)
    else:
        st.info("Belum ada data klien.")


# --- 3. MENU: SUPPLIER ---
elif menu == "Supplier":
    st.subheader("🚚 Manajemen Master Supplier")
    with st.form("form_supplier"):
        nama_s = st.text_input("Nama Supplier / Toko")
        kontak_s = st.text_input("Kontak / Alamat Supplier")
        submit_s = st.form_submit_button("Simpan Supplier Baru")

        if submit_s:
            if nama_s and kontak_s:
                data_supplier.append({"nama": nama_s, "kontak": kontak_s})
                save_data(FILE_SUPPLIER, data_supplier)
                st.success(f"Supplier '{nama_s}' berhasil disimpan!")
                st.rerun()
            else:
                st.error("Nama dan Kontak wajib diisi!")

    st.write("### Daftar Supplier Tersimpan")
    if data_supplier:
        st.table(data_supplier)
    else:
        st.info("Belum ada data supplier.")


# --- 4. MENU: STOK & BARANG ---
elif menu == "Stok & Barang":
    st.subheader("📦 Manajemen Stok, Barang & Stock Card")
    tab_barang, tab_card, tab_adjust = st.tabs(["Master Barang", "Stock Card", "Adjustment Stok"])

    with tab_barang:
        with st.form("form_barang"):
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                nama_b = st.text_input("Nama Barang / Jasa")
                harga_b = st.number_input("Harga Jual (Rp)", min_value=0.0, value=0.0, step=1000.0)
            with col_b2:
                stok_b = st.number_input("Stok Awal", min_value=0, value=0, step=1)
                kelola_stok_b = st.checkbox("Barang fisik / ikut kontrol stok", value=True)
            submit_b = st.form_submit_button("Simpan Barang")

            if submit_b:
                nama_b = nama_b.strip()
                if not nama_b:
                    st.error("Nama barang wajib diisi!")
                elif _find_barang(nama_b):
                    st.error("Barang dengan nama tersebut sudah ada.")
                else:
                    data_barang.append({
                        "nama": nama_b, "harga": float(harga_b), "stok": int(stok_b),
                        "stok_awal": int(stok_b), "kelola_stok": bool(kelola_stok_b),
                    })
                    save_data(FILE_BARANG, data_barang)
                    ensure_stock_opening_ledger()
                    st.success(f"Barang '{nama_b}' berhasil disimpan!")
                    st.rerun()

        st.write("### Daftar Stok Barang")
        if data_barang:
            tabel_barang = []
            for b in data_barang:
                stok = int(b.get("stok", 0) or 0)
                status_stok = "JASA / NON-STOCK" if not b.get("kelola_stok", True) else ("🔴 HABIS" if stok <= 0 else "🟢 AMAN")
                tabel_barang.append({
                    "Nama": b.get("nama", ""),
                    "Harga Jual": f"Rp {b.get('harga', 0):,.0f}",
                    "Stok": stok,
                    "Status": status_stok,
                })
            st.dataframe(tabel_barang, use_container_width=True, hide_index=True)
        else:
            st.info("Belum ada data barang.")

    with tab_card:
        ledger = load_stock_card()
        names_card = [b.get("nama", "") for b in data_barang if b.get("nama")]
        filter_card = st.selectbox("Pilih Barang", ["Semua Barang"] + names_card)
        rows = ledger if filter_card == "Semua Barang" else [x for x in ledger if x.get("barang") == filter_card]
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("Belum ada transaksi stock card.")

    with tab_adjust:
        st.write("### Koreksi / Stock Opname")
        with st.form("form_adjustment_stok"):
            names_adj = [b.get("nama", "") for b in data_barang if b.get("kelola_stok", True)]
            pilih_adj = st.selectbox("Barang", names_adj if names_adj else ["(Belum ada)"])
            stok_sekarang = _find_barang(pilih_adj)
            stok_display = int(stok_sekarang.get("stok", 0)) if stok_sekarang else 0
            st.metric("Stok Saat Ini", stok_display)
            stok_fisik = st.number_input("Stok Fisik / Opname", min_value=0, value=stok_display, step=1)
            ket_adj = st.text_input("Keterangan", value="Koreksi opname")
            submit_adj = st.form_submit_button("Simpan Adjustment")
            if submit_adj:
                selisih = int(stok_fisik) - int(stok_display)
                if selisih != 0:
                    apply_stock_movement(pilih_adj, qty_masuk=selisih if selisih > 0 else 0, qty_keluar=abs(selisih) if selisih < 0 else 0, jenis="ADJUSTMENT", keterangan=ket_adj)
                    st.success("Adjustment stok berhasil disimpan!")
                    st.rerun()


# --- 5. MENU: PEMBELIAN ---
elif menu == "Pembelian":
    st.subheader("🛒 Catat Pembelian (Stok Otomatis Bertambah)")
    with st.form("form_pembelian"):
        tgl_pb = st.text_input("Tanggal Beli", value=datetime.now().strftime("%d-%m-%Y"))
        sup_list = [s["nama"] for s in data_supplier] if data_supplier else []
        pilih_sup = st.selectbox("Supplier", sup_list if sup_list else ["(Belum ada)"])
        bar_list = [b["nama"] for b in data_barang] if data_barang else []
        pilih_bar = st.selectbox("Barang", bar_list if bar_list else ["(Belum ada)"])
        qty_pb = st.number_input("Qty Beli", min_value=1, value=1)
        harga_pb = st.number_input("Harga Beli Satuan (Rp)", min_value=0.0, value=0.0, step=1000.0)
        submit_pb = st.form_submit_button("Simpan Pembelian & Update Stok")

        if submit_pb:
            if pilih_sup != "(Belum ada)" and pilih_bar != "(Belum ada)":
                no_pb = f"PB-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                apply_stock_movement(pilih_bar, qty_masuk=int(qty_pb), jenis="STOK MASUK", referensi=no_pb, keterangan=f"Beli dari {pilih_sup}", tanggal=tgl_pb)
                data_pembelian.append({"no_pembelian": no_pb, "tanggal": tgl_pb, "supplier": pilih_sup, "nama": pilih_bar, "qty": qty_pb, "harga": harga_pb, "total": qty_pb * harga_pb})
                save_data(FILE_PEMBELIAN, data_pembelian)
                st.success("Pembelian berhasil dicatat dan stok bertambah!")
                st.rerun()


# --- 6. MENU: REKAP & PIUTANG ---
elif menu == "Rekap & Piutang":
    st.subheader("📊 Ringkasan Keuangan & Pengelolaan Riwayat Dokumen")

    if data_invoice_history:
        jenis_filter = st.selectbox("Filter Jenis Dokumen", ["Semua", "Invoice", "Quotation / Penawaran", "Surat Jalan", "Purchase Order", "Tanda Terima"])
        status_filter = st.selectbox("Filter Status Pembayaran", ["Semua", "Belum Lunas (Piutang)", "Lunas"])

        for idx, inv in enumerate(data_invoice_history):
            jenis_inv = _infer_jenis_dokumen(inv)
            status_inv = inv.get("status", "Belum Lunas (Piutang)")
            if jenis_filter != "Semua" and jenis_inv != jenis_filter:
                continue
            if status_filter != "Semua" and status_inv != status_filter:
                continue

            nomor_inv = inv.get("no_dokumen") or inv.get("no_inv") or "-"
            with st.expander(f"📁 {jenis_inv} | {nomor_inv} | Klien: {inv.get('klien')} | Total: Rp {float(inv.get('grand_total', 0) or 0):,.0f} | Status: {status_inv}"):
                st.write(f"**Status Pembayaran:** {status_inv}")
                if status_inv == "Belum Lunas (Piutang)":
                    if st.button(f"✅ Lunasi Piutang ({nomor_inv})", key=f"pelunasan_{idx}"):
                        inv["status"] = "Lunas"
                        save_data(FILE_INVOICE, data_invoice_history)
                        st.success("Status dokumen diubah menjadi Lunas!")
                        st.rerun()

                if st.button("🗑 Hapus Dokumen", key=f"del_inv_{idx}"):
                    data_invoice_history.pop(idx)
                    save_data(FILE_INVOICE, data_invoice_history)
                    st.success("Dokumen berhasil dihapus!")
                    st.rerun()
    else:
        st.info("Belum ada riwayat dokumen.")


# --- 7. MENU: LAPORAN PAJAK ---
elif menu == "Laporan Pajak":
    st.subheader("🏛️ Laporan Pajak (PPN & PPh) & Ekspor e-Faktur CSV")
    
    total_ppn = 0.0
    pajak_rows = []

    for inv in data_invoice_history:
        jenis_inv = _infer_jenis_dokumen(inv)
        if jenis_inv not in ["Invoice", "Quotation / Penawaran"]:
            continue
        dpp = float(inv.get("subtotal", 0) or 0)
        ppn = float(inv.get("ppn", 0) or 0)
        total_ppn += ppn
        pajak_rows.append({
            "Tanggal": inv.get("tanggal"),
            "No_Dokumen": inv.get("no_dokumen") or inv.get("no_inv"),
            "Klien": inv.get("klien"),
            "DPP": dpp,
            "PPN": ppn,
        })

    st.metric("Total PPN Tersimpan", f"Rp {total_ppn:,.0f}")
    if pajak_rows:
        df_pajak = pd.DataFrame(pajak_rows)
        st.dataframe(df_pajak, use_container_width=True)

        csv_efaktur = df_pajak.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Format e-Faktur CSV (DJPP)",
            data=csv_efaktur,
            file_name="efaktur_nagami.csv",
            mime="text/csv",
        )
    else:
        st.info("Belum ada data pajak.")


# --- 8. MENU: BACKUP / RESTORE ---
elif menu == "Backup/Restore":
    st.subheader("💾 Backup dan Restore Data Sistem")
    all_data = {
        "klien": data_klien, "supplier": data_supplier, "barang": data_barang,
        "pembelian": data_pembelian, "invoice": data_invoice_history,
        "config": load_data(FILE_CONFIG), "counter": _load_counter_dokumen(),
    }
    st.download_button("📥 Download Backup JSON", data=json.dumps(all_data, indent=4, ensure_ascii=False), file_name="backup_nagami.json", mime="application/json")


# --- 9. MENU: PENGATURAN PERUSAHAAN & LOGO ---
elif menu == "Pengaturan Perusahaan & Logo":
    st.subheader("⚙️ Pengaturan Profil Perusahaan & Kop Surat")
    profil_curr = load_data(FILE_PROFIL, DEFAULT_PROFIL)

    with st.form("form_profil"):
        p_nama = st.text_input("Nama Perusahaan", value=profil_curr.get("nama_perusahaan"))
        p_tagline = st.text_input("Gedung / Lokasi", value=profil_curr.get("tagline"))
        p_alamat = st.text_area("Alamat Lengkap", value=profil_curr.get("alamat"))
        p_email = st.text_input("Email Resmi", value=profil_curr.get("email"))
        p_telp = st.text_input("No. Telepon", value=profil_curr.get("telp"))
        p_direktur = st.text_input("Nama Penanggung Jawab / Direktur", value=profil_curr.get("direktur"))

        uploaded_logo = st.file_uploader("Unggah Logo Perusahaan Baru (PNG/JPG)", type=["png", "jpg", "jpeg"])
        submit_profil = st.form_submit_button("💾 Simpan Profil & Logo Baru", type="primary")

        if submit_profil:
            new_profil = {
                "nama_perusahaan": p_nama, "tagline": p_tagline, "alamat": p_alamat,
                "email": p_email, "telp": p_telp, "direktur": p_direktur,
            }
            save_data(FILE_PROFIL, new_profil)
            if uploaded_logo is not None:
                with open("logo_nagami.png", "wb") as f:
                    f.write(uploaded_logo.getbuffer())
                st.success("Logo baru berhasil disimpan!")
            st.success("Profil perusahaan berhasil diperbarui!")
            st.rerun()

    if os.path.exists("logo_nagami.png"):
        st.image("logo_nagami.png", width=160, caption="Logo Aktif")


# --- 10. MENU: KONFIGURASI SMTP ---
elif menu == "Konfigurasi SMTP (Email)":
    st.subheader("⚙️ Konfigurasi Server SMTP untuk Kirim Email")
    smtp_curr = load_data(FILE_SMTP, DEFAULT_SMTP)

    with st.form("form_smtp"):
        st.write("Atur server pengirim email (misal: Gmail dengan App Password atau SMTP Hosting Perusahaan).")
        s_server = st.text_input("SMTP Server Host (misal: smtp.gmail.com atau mail.namadomain.com)", value=smtp_curr.get("server", "smtp.gmail.com"))
        s_port = st.number_input("SMTP Port (465 untuk SSL, 587 untuk TLS)", value=int(smtp_curr.get("port", 465)), step=1)
        s_sender = st.text_input("Email Pengirim", value=smtp_curr.get("sender", ""))
        s_password = st.text_input("Password / App Password (16-Digit untuk Gmail)", type="password", value=smtp_curr.get("password", ""))

        submit_smtp = st.form_submit_button("💾 Simpan Pengaturan SMTP", type="primary")
        if submit_smtp:
            new_smtp = {
                "server": s_server,
                "port": int(s_port),
                "sender": s_sender,
                "password": s_password,
            }
            save_data(FILE_SMTP, new_smtp)
            st.success("Konfigurasi SMTP berhasil disimpan!")
            st.rerun()