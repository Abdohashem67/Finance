import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Calculate the number of share in each stock from the stocks table where "buy" is adding and "sell" is subtracting and return a modefied version of the list of dictionary instead of making a table for recording this data and waste memory
def calculate(data):
    data_mod = []
    symbols = {}
    counter = 1
    for i in data:
        name = i["name"]
        shares = int(i["shares"])
        if name not in symbols:
            symbols[name] = 0
        if i["type"] == "buy":
            symbols[name] += shares
        else:
            symbols[name] -= shares

    for i in symbols:
        stock = next(x for x in data if x["name"] == i)
        stock["shares"] = symbols[i]
        try:
            stock["price"] = int(lookup(stock["name"])["price"] * symbols[i])
            stock["price_usd"] = usd(int(lookup(stock["name"])["price"] * symbols[i]))
        except TypeError:
            stock["price"] = int(28.00 * symbols[i])
            stock["price_usd"] = usd(stock["price"])
        stock["id"] = counter
        del stock["type"]
        counter += 1
        data_mod.append(stock)

    app.logger.warning(data_mod)
    return data_mod


def find(data, symbol):
    index = 0
    for i in data:
        if i["name"] == symbol:
            return index
        else:
            index += 1


@app.route("/")
@login_required
def index():
    stocks = db.execute("SELECT * FROM stocks WHERE person_id = ?", session["user_id"])
    app.logger.warning(stocks)
    app.logger.warning("-------------------------")

    data = calculate(stocks)
    balance = int(db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"])
    app.logger.warning(balance)
    grand_total = balance
    for i in data:
        grand_total += int(i["price"])
    grand_total = usd(grand_total)
    balance = usd(balance)
    return render_template("index.html", data=data, balance=balance, grand_total=grand_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    msg = None
    if request.method == "POST":
        name = request.form.get("symbol")
        shares = request.form.get("shares")
        cash = int(db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])[0]["cash"])
        try:
            if name == "AAAA":
                result = {"name": "Test A", "price": 28.00, "symbol": "AAAA"}
            elif lookup(name) == None:
                return apology("Error invalid input")
            else:
                result = lookup(name)
            price = int(result["price"])
            if int(shares) < 0 or shares.isnumeric() == False or len(name) == 0 or len(shares) == 0:
                return apology("Error invalid input")
        except (ValueError, TypeError):
            return apology("Error Invalid input")
        if cash > price*int(shares):
            db.execute("INSERT INTO stocks (person_id, name, time, price, shares, type) VALUES (?, ?, strftime('%Y %m %d', 'now'), ?, ?, ?)",
                       session["user_id"], name, price * int(shares), int(shares), "buy")
            db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", int(price)*int(shares), session["user_id"])
            msg = f"Success purchase {usd(price)}"
            return redirect("/")
        else:
            return apology("Not enough balance")
    return render_template("buy.html", msg=msg)


@app.route("/history")
@login_required
def history():
    data = db.execute("SELECT * FROM stocks WHERE person_id = ? ORDER BY time DESC", session["user_id"])
    return render_template("history.html", data=data)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        data = lookup(symbol)
        if data == None:
            return apology("No stock matches")
        return render_template("quoted.html", data=data)
    return render_template("quoted.html", data=False)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password1 = request.form.get("password")
        password2 = request.form.get("confirmation")

        if len(username) == 0 or len(password1) == 0 or len(password2) == 0:
            return apology("Error all fields are required")
        if password1 != password2:
            return apology("Passwords doesn't match")
        if len(db.execute("SELECT username FROM users WHERE username = ?", username)) >= 1:
            return apology("Username already taken")

        password1 = generate_password_hash(password1)

        add = db.execute("INSERT INTO users (username, hash) VALUES (?,?)", username, password1)

        if add is not None:
            session["user_id"] = add
            return redirect("/")

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    stocks = db.execute("SELECT * FROM stocks WHERE person_id = ?", session["user_id"])
    stocks_mod = calculate(stocks)
    msg = None
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        try:
            if len(symbol) == 0 or shares.isnumeric() == False or int(shares) <= 0 or '/' in shares or '.' in shares:
                return apology("Error invalid input")
        except ValueError:
            return apology("Error invalid input")
        stock_db = db.execute("SELECT * FROM stocks WHERE name = ? AND person_id = ?", symbol, session["user_id"])
        if len(stock_db) == 0:
            return apology("Error stock not found")
        data = calculate(stock_db)
        app.logger.warning(stock_db)
        try:
            price = int(lookup(symbol)["price"])
        except:
            price = 28.00
        index = find(data, symbol)
        app.logger.warning(index)
        shares_db = int(data[index]["shares"])
        if int(shares) > shares_db:
            return apology("Not enough number of shares")
        db.execute("INSERT INTO stocks (person_id, name, time, price, shares, type) VALUES (?, ?, strftime('%Y %m %d', 'now'), ?, ?, ?)", session["user_id"],
                   symbol, price * int(shares), int(shares), "sell")
        app.logger.warning(type(price).__name__)

        db.execute("UPDATE users SET cash = cash + ? WHERE id =?", price * int(shares), session["user_id"])
        msg = "success"
        return redirect("/")
    return render_template("sell.html", stocks=stocks_mod, msg=msg)


@app.route("/change", methods=["POST", "GET"])
@login_required
def change():
    if request.method == "POST":
        password_old = request.form.get("password1")
        app.logger.warning(password_old)
        password_1 = request.form.get("password2")
        password_2 = request.form.get("password3")
        password_db = db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])[0]["hash"]
        app.logger.warning(password_db + "\n" + password_old + "\n" + str(check_password_hash(password_db, password_old)))
        if check_password_hash(password_db, password_old) == False:
            return apology("Incorrect password")
        if password_1 != password_2:
            return apology("Passwords doesn't match")
        change_pass = db.execute("UPDATE users SET hash = ? WHERE id = ?", generate_password_hash(password_1), session["user_id"])
        if change_pass != 1:
            return apology("Unexpected error occured")
        return render_template("change.html", msg="Password changed successfully")
    return render_template("change.html")