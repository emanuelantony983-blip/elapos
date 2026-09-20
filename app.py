from datetime import datetime, timedelta
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, flash, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "elapos_secret_key_2026")


def get_db_connection():
  database_url = os.environ.get("DATABASE_URL")
  if database_url:
    # Render mara nyingi hutoa link inayoanza na postgres:// lakini psycopg2 inataka postgresql://
    if database_url.startswith("postgres://"):
      database_url = database_url.replace("postgres://", "postgresql://", 1)
    conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
  else:
    # Hii ni kama mtu anaiendesha locally kwenye kompyuta yake na hana DATABASE_URL
    import sqlite3

    conn = sqlite3.connect("elapos.db")
  return conn


def init_db():
  conn = get_db_connection()
  cursor = conn.cursor()

  # Uundaji wa maboksi (tables) kwa ajili ya PostgreSQL au SQLite
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            shop_name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            password TEXT NOT NULL,
            status TEXT DEFAULT 'pending'
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            name TEXT NOT NULL,
            buying_price REAL NOT NULL,
            selling_price REAL NOT NULL,
            quantity REAL NOT NULL
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            product_name TEXT NOT NULL,
            quantity_sold REAL NOT NULL,
            buying_total REAL NOT NULL,
            selling_total REAL NOT NULL,
            profit REAL NOT NULL,
            sale_date TEXT NOT NULL
        )
    """)
  conn.commit()
  conn.close()
# Hii inaita kazi hiyo mara programu inapowashwa
init_db()

@app.before_request
def check_pending_status():
  if "user_id" in session:
    if request.endpoint in [
        "admin_panel",
        "approve_user",
        "logout",
        "pending_payment",
        "static",
    ]:
      return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT status, username FROM users WHERE id = %s",
        (session["user_id"],),
    )
    user = cursor.fetchone()
    conn.close()

    if user:
      # Inategemea na cursor kama inarudisha dictionary au tuple
      status = user["status"] if isinstance(user, dict) else user[0]
      username = user["username"] if isinstance(user, dict) else user[1]
      if status == "pending" and username != "admin":
        return redirect(url_for("pending_payment"))


@app.route("/")
def home():
  return render_template("index.html")


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        shop_name = request.form.get('shop_name')
        username = request.form.get('username')
        password = request.form.get('password')
        phone = request.form.get('phone')
        
        current_date = datetime.now()
        expiry_date = (current_date + timedelta(days=30)).strftime('%Y-%m-%d')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO users (shop_name, username, password, phone, expiry, status) VALUES (%s, %s, %s, %s, %s, %s)",
            (shop_name, username, password, phone, expiry_date, 'pending')
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return redirect(url_for('pending_payment'))
        
    return render_template('register.html')
           
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        # Tumeongeza 'expiry' kwenye SQL query hapa chini
        cursor.execute(
            "SELECT id, username, password, status, expiry FROM users WHERE username = %s",
            (username,),
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            u_id = user["id"] if isinstance(user, dict) else user[0]
            u_name = user["username"] if isinstance(user, dict) else user[1]
            u_pass = user["password"] if isinstance(user, dict) else user[2]
            u_status = user["status"] if isinstance(user, dict) else user[3]
            u_expiry = user["expiry"] if isinstance(user, dict) else user[4]

            if u_pass == password:
                session["user_id"] = u_id
                session["username"] = u_name

                # Admin anapita moja kwa moja bila vizuizi
                if u_name == "admin":
                    return redirect(url_for("dashboard"))

                # Angalia kama status ni pending au kama siku 30 zimeisha
                if u_status == "pending":
                    return redirect(url_for("pending_payment"))
                
                # Hapa tunaweza kuongeza ukaguzi wa siku 30 za expiry kama zimepita
                if u_expiry:
                    from datetime import datetime
                    expiry_date = datetime.strptime(str(u_expiry), "%Y-%m-%d")
                    if datetime.now() > expiry_date:
                        return redirect(url_for("pending_payment"))

                return redirect(url_for("dashboard"))
            else:
                flash("Taarifa si sahihi!")
        else:
            flash("Taarifa si sahihi!")

    return render_template("login.html")
           

@app.route("/pending")
def pending_payment():
  payment_number = "Airtel Money - 0680778594"
  whatsapp_url = (
      "https://wa.me/255680778594?text=Habari%20Admin,%20nimefanya%20malipo%20ya%20ELAPOS,%20naomba%20kuidhinishiwa%20akaunti%20yangu."
  )
  return render_template(
      "pending_payment.html",
      payment_number=payment_number,
      whatsapp_url=whatsapp_url,
  )


@app.route("/admin")
def admin_panel():
  if "user_id" not in session:
    return redirect(url_for("login"))

  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute("SELECT id, shop_name, username, phone, status FROM users")
  users = cursor.fetchall()
  conn.close()

  rows = ""
  for u in users:
    u_id = u["id"] if isinstance(u, dict) else u[0]
    u_shop = u["shop_name"] if isinstance(u, dict) else u[1]
    u_uname = u["username"] if isinstance(u, dict) else u[2]
    u_phone = u["phone"] if isinstance(u, dict) else u[3]
    u_stat = u["status"] if isinstance(u, dict) else u[4]

    status_color = "green" if u_stat == "active" else "orange"
    action_btn = (
        f"<a href='/admin/approve/{u_id}' style='background:green; color:white;"
        " padding:5px 10px; text-decoration:none;"
        " border-radius:4px;'>Idhinisha</a>"
        if u_stat == "pending"
        else "Tayari"
    )
    rows += (
        f"<tr><td>{u_id}</td><td>{u_shop}</td><td>{u_uname}</td><td>{u_phone}</td><td"
        f" style='color:{status_color}; font-weight:bold;'>{u_stat}</td><td>{action_btn}</td></tr>"
    )

  return f"""
    <html>
    <head><title>ELAPOS - Admin Panel</title></head>
    <body style="font-family:Arial; padding:20px; background:#f4f4f9;">
        <h2>Usimamizi wa ELAPOS (Admin Panel)</h2>
        <p><a href="/dashboard">Nenda Dashboard</a> | <a href="/logout">Logout</a></p>
        <table border="1" cellpadding="10" cellspacing="0" style="background:white; width:100%; border-collapse:collapse;">
            <tr style="background:#ddd;"><th>ID</th><th>Duka</th><th>Username</th><th>Simu</th><th>Status</th><th>Vitendo</th></tr>
            {rows}
        </table>
    </body>
    </html>
    """


@app.route("/admin/approve/<int:user_id>")
def approve_user(user_id):
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE users SET status = 'active' WHERE id = %s", (user_id,)
  )
  conn.commit()
  conn.close()
  return redirect(url_for("admin_panel"))


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
  if "user_id" not in session:
    return redirect(url_for("login"))

  user_id = session["user_id"]
  conn = get_db_connection()
  cursor = conn.cursor()

  if request.method == "POST" and "add_product" in request.form:
    name = request.form["name"]
    buying_price = float(request.form["buying_price"])
    selling_price = float(request.form["selling_price"])
    quantity = float(request.form["quantity"])

    cursor.execute(
        "INSERT INTO products (user_id, name, buying_price, selling_price,"
        " quantity) VALUES (%s, %s, %s, %s, %s)",
        (user_id, name, buying_price, selling_price, quantity),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))

  if request.method == "POST" and "sell_product" in request.form:
    prod_id = int(request.form["prod_id"])
    qty_sold = float(request.form["qty_sold"])
    custom_selling_price = request.form["custom_selling_price"]

    cursor.execute(
        "SELECT name, buying_price, selling_price, quantity FROM products WHERE"
        " id = %s AND user_id = %s",
        (prod_id, user_id),
    )
    prod = cursor.fetchone()

    if prod:
      p_name = prod["name"] if isinstance(prod, dict) else prod[0]
      b_price = prod["buying_price"] if isinstance(prod, dict) else prod[1]
      s_price_default = (
          prod["selling_price"] if isinstance(prod, dict) else prod[2]
      )
      p_qty = prod["quantity"] if isinstance(prod, dict) else prod[3]

      if p_qty >= qty_sold:
        if custom_selling_price and custom_selling_price.strip() != "":
          s_price = float(custom_selling_price)
        else:
          s_price = s_price_default

        new_qty = p_qty - qty_sold
        buying_total = b_price * qty_sold
        selling_total = s_price * qty_sold
        profit = selling_total - buying_total
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")

        cursor.execute(
            "UPDATE products SET quantity = %s WHERE id = %s",
            (new_qty, prod_id),
        )
        cursor.execute(
            "INSERT INTO sales (user_id, product_name, quantity_sold,"
            " buying_total, selling_total, profit, sale_date) VALUES (%s, %s,"
            " %s, %s, %s, %s, %s)",
            (
                user_id,
                p_name,
                qty_sold,
                buying_total,
                selling_total,
                profit,
                current_time,
            ),
        )
        conn.commit()

    conn.close()
    return redirect(url_for("dashboard"))

  cursor.execute(
      "SELECT id, name, buying_price, selling_price, quantity FROM products"
      " WHERE user_id = %s",
      (user_id,),
  )
  products = cursor.fetchall()

  cursor.execute(
      "SELECT product_name, quantity_sold, selling_total, profit, sale_date"
      " FROM sales WHERE user_id = %s ORDER BY id DESC",
      (user_id,),
  )
  sales = cursor.fetchall()

  cursor.execute(
      "SELECT SUM(profit), SUM(selling_total) FROM sales WHERE user_id = %s",
      (user_id,),
  )
  totals = cursor.fetchone()
  t_profit = (
      totals["sum"]
      if isinstance(totals, dict)
      else (totals[0] if totals else 0)
  )
  t_sales = (
      totals["sum"]
      if isinstance(totals, dict)
      else (totals[1] if totals else 0)
  )
  total_profit = t_profit if t_profit is not None else 0.0
  total_sales = t_sales if t_sales is not None else 0.0

  today_str = datetime.now().strftime("%Y-%m-%d")
  cursor.execute(
      "SELECT SUM(profit), SUM(selling_total) FROM sales WHERE user_id = %s AND"
      " sale_date LIKE %s",
      (user_id, f"{today_str}%"),
  )
  today_totals = cursor.fetchone()
  tp = (
      today_totals["sum"]
      if isinstance(today_totals, dict)
      else (today_totals[0] if today_totals else 0)
  )
  ts = (
      today_totals["sum"]
      if isinstance(today_totals, dict)
      else (today_totals[1] if today_totals else 0)
  )
  today_profit = tp if tp is not None else 0.0
  today_sales = ts if ts is not None else 0.0

  month_str = datetime.now().strftime("%Y-%m")
  cursor.execute(
      "SELECT SUM(profit), SUM(selling_total) FROM sales WHERE user_id = %s AND"
      " sale_date LIKE %s",
      (user_id, f"{month_str}%"),
  )
  month_totals = cursor.fetchone()
  mp = (
      month_totals["sum"]
      if isinstance(month_totals, dict)
      else (month_totals[0] if month_totals else 0)
  )
  ms = (
      month_totals["sum"]
      if isinstance(month_totals, dict)
      else (month_totals[1] if month_totals else 0)
  )
  month_profit = mp if mp is not None else 0.0
  month_sales = ms if ms is not None else 0.0

  conn.close()

  prod_options = ""
  for p in products:
    p_id = p["id"] if isinstance(p, dict) else p[0]
    p_name = p["name"] if isinstance(p, dict) else p[1]
    p_sprice = p["selling_price"] if isinstance(p, dict) else p[3]
    p_qty = p["quantity"] if isinstance(p, dict) else p[4]
    prod_options += (
        f"<option value='{p_id}'>{p_name} (Zilizopo: {p_qty}, Bei:"
        f" {p_sprice}/=)</option>"
    )

  prod_rows = ""
  for p in products:
    p_id = p["id"] if isinstance(p, dict) else p[0]
    p_name = p["name"] if isinstance(p, dict) else p[1]
    p_bprice = p["buying_price"] if isinstance(p, dict) else p[2]
    p_sprice = p["selling_price"] if isinstance(p, dict) else p[3]
    p_qty = p["quantity"] if isinstance(p, dict) else p[4]
    prod_rows += (
        f"<tr><td>{p_name}</td><td>{p_bprice}/=</td><td>{p_sprice}/=</td><td>{p_qty}</td><td><a"
        f" href='/delete_product/{p_id}' onclick='return confirm(\"Una hakika"
        " unataka kufuta bidhaa hii?\");' style='color:red;"
        " text-decoration:none; font-weight:bold;'>Futa</a></td></tr>"
    )

  sales_rows = ""
  for s in sales:
    s_name = s["product_name"] if isinstance(s, dict) else s[0]
    s_qty = s["quantity_sold"] if isinstance(s, dict) else s[1]
    s_stotal = s["selling_total"] if isinstance(s, dict) else s[2]
    s_profit = s["profit"] if isinstance(s, dict) else s[3]
    s_date = s["sale_date"] if isinstance(s, dict) else s[4]
    sales_rows += (
        f"<tr><td>{s_date}</td><td>{s_name}</td><td>{s_qty}</td><td>{s_stotal}/=</td><td"
        f" style='color: {'green' if s_profit >= 0 else 'red'};"
        f" font-weight:bold;'>{s_profit}/=</td></tr>"
    )

  return f"""
    <html>
    <head><title>ELAPOS - Duka Lako</title></head>
    <body style="font-family:Arial; padding:20px; background:#f4f4f9;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <h1>ELAPOS - Mfumo wa Mauzo na Faida</h1>
            <div>
                <a href="/admin" style="margin-right:15px; text-decoration:none; font-weight:bold;">Admin Panel</a>
                <a href="/logout" style="color:red; text-decoration:none; font-weight:bold;">Toka nje (Logout)</a>
            </div>
        </div>
        <hr>
        
        <div style="display: flex; gap: 20px; flex-wrap: wrap;">
            <div style="background:white; padding:20px; border-radius:8px; flex:1; min-width:300px; box-shadow:0 2px 5px rgba(0,0,0,0.1);">
                <h3>Weka Bidhaa Mpya Stoku</h3>
                <form method="POST">
                    <input type="hidden" name="add_product" value="1">
                    <p><input type="text" name="name" placeholder="Jina la Bidhaa (Mf: Sukari)" required style="width:100%; padding:8px;"></p>
                    <p><input type="number" step="any" name="buying_price" placeholder="Bei ya Kununulia (Mtaji)" required style="width:100%; padding:8px;"></p>
                    <p><input type="number" step="any" name="selling_price" placeholder="Bei ya Kuuzia ya Kawaida" required style="width:100%; padding:8px;"></p>
                    <p><input type="number" step="any" name="quantity" placeholder="Idadi / Kiasi (Mf: 10.5)" required style="width:100%; padding:8px;"></p>
                    <button type="submit" style="background:#007bff; color:white; border:none; padding:10px 15px; cursor:pointer; border-radius:4px; font-weight:bold;">Hifadhi Bidhaa</button>
                </form>
            </div>

            <div style="background:white; padding:20px; border-radius:8px; flex:1; min-width:300px; box-shadow:0 2px 5px rgba(0,0,0,0.1);">
                <h3>Fanya Mauzo (POS)</h3>
                <form method="POST">
                    <input type="hidden" name="sell_product" value="1">
                    <p>
                        Chagua Bidhaa:<br>
                        <select name="prod_id" required style="width:100%; padding:8px; margin-top:5px;">
                            {prod_options}
                        </select>
                    </p>
                    <p><input type="number" step="any" name="qty_sold" placeholder="Idadi inayouzwa (Mf: 1.5)" required style="width:100%; padding:8px;"></p>
                    <p><input type="number" step="any" name="custom_selling_price" placeholder="Bei maalum ya kuuzia (Hiari -acha wazi kama ni bei ya kawaida)" style="width:100%; padding:8px;"></p>
                    <button type="submit" style="background:green; color:white; border:none; padding:10px 15px; cursor:pointer; border-radius:4px; font-weight:bold;">Uza Sasa</button>
                </form>
            </div>
        </div>

        <div style="display: flex; gap: 20px; flex-wrap: wrap; margin-top: 20px;">
            <div style="background:#e3f2fd; padding:15px; border-radius:8px; flex:1; min-width:250px;">
                <h3>Mauzo ya Leo</h3>
                <p style="font-size:16px;">Jumla ya Mauzo: <b>{today_sales}/=</b></p>
                <p style="font-size:16px;">Faida ya Leo: <b style="color: {'green' if today_profit >= 0 else 'red'};">{today_profit}/=</b></p>
            </div>
            <div style="background:#e8f5e9; padding:15px; border-radius:8px; flex:1; min-width:250px;">
                <h3>Ripoti ya Mwezi Huu</h3>
                <p style="font-size:16px;">Jumla ya Mauzo: <b>{month_sales}/=</b></p>
                <p style="font-size:16px;">Faida ya Mwezi: <b style="color: {'green' if month_profit >= 0 else 'red'};">{month_profit}/=</b></p>
            </div>
            <div style="background:#fff3e0; padding:15px; border-radius:8px; flex:1; min-width:250px;">
                <h3>Jumla Kuu (All-Time)</h3>
                <p style="font-size:16px;">Jumla ya Mauzo: <b>{total_sales}/=</b></p>
                <p style="font-size:16px;">Jumla ya Faida: <b style="color: {'green' if total_profit >= 0 else 'red'};">{total_profit}/=</b></p>
            </div>
        </div>

        <div style="display: flex; gap: 20px; flex-wrap: wrap; margin-top: 20px;">
            <div style="background:white; padding:20px; border-radius:8px; flex:1; min-width:300px; box-shadow:0 2px 5px rgba(0,0,0,0.1);">
                <h3>Bidhaa Zilizopo Stoku</h3>
                <table border="1" cellpadding="8" cellspacing="0" style="width:100%; border-collapse:collapse;">
                    <tr style="background:#eee;"><th>Bidhaa</th><th>Mtaji</th><th>Bei ya Kuuzia</th><th>Zilizobaki</th><th>Kitendo</th></tr>
                    {prod_rows}
                </table>
            </div>

            <div style="background:white; padding:20px; border-radius:8px; flex:1; min-width:300px; box-shadow:0 2px 5px rgba(0,0,0,0.1);">
                <h3>Historia ya Mauzo & Faida</h3>
                <table border="1" cellpadding="8" cellspacing="0" style="width:100%; border-collapse:collapse;">
                    <tr style="background:#eee;"><th>Tarehe & Saa</th><th>Bidhaa</th><th>Idadi</th><th>Pesa</th><th>Faida / Hasara</th></tr>
                    {sales_rows}
                </table>
            </div>
        </div>
    </body>
    </html>
    """


@app.route("/delete_product/<int:prod_id>")
def delete_product(prod_id):
  if "user_id" not in session:
    return redirect(url_for("login"))

  user_id = session["user_id"]
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute(
      "DELETE FROM products WHERE id = %s AND user_id = %s", (prod_id, user_id)
  )
  conn.commit()
  conn.close()
  return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
  session.clear()
  return redirect(url_for("login"))


if __name__ == "__main__":
  init_db()
  port = int(os.environ.get("PORT", 5001))
  app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)

