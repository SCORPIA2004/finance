import os
import datetime

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
# postgres://uquzjppvrwlupx:62c0d50de674f9cfa1345454b08c640ceaf21a3cdae91e598382f577fc40ee88@ec2-52-207-15-147.compute-1.amazonaws.com:5432/d3e2va1ml9ivv3

uri = os.getenv("DATABASE_URL")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://")
db = SQL(uri)

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


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # user has done some transactions
    totalvalue = 0.00
    # returns a list of dictionaries of {user_id: # }
    idDictList = db.execute("SELECT user_id FROM transactions")
    # make a list containing just the user_id's
    idList=[]
    # for eevry dict in idDictList
    for id in idDictList:
        idList.append(id["user_id"])

    if session["user_id"] in idList:
        # I can get all the stocks that have current user's ID
        data = db.execute("SELECT * FROM transactions WHERE user_id=?", session["user_id"])

        # need to get current price of stocks
        for stock in data:
            temp = lookup(stock["symbol"])
            stock["unit_cost"] = temp["price"]
            stock["total_cost"] = stock["unit_cost"] * stock["shares"]
            totalvalue += stock["total_cost"]
            stock["total_cost"] = usd(stock["total_cost"])
            # user stats:
        user = db.execute("SELECT * FROM users WHERE id=?", session["user_id"])
        cash = user[0]["cash"]
        name = user[0]["username"]
        totalvalue = usd(cash + totalvalue)
        cashusd = usd(cash)

        return render_template("index.html", data=data, cashusd=cashusd, totalvalue=totalvalue, name=name)

    # else user has not yet made any transactions
    else:
        return render_template("registered.html")



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # purchase stock if user can afford it
    if request.method == "POST":
        x = datetime.datetime.now()
        second = x.second
        minute = x.minute
        hour = x.hour
        day = x.day
        month = x.month
        year = x.year

        # --- VALIDATE Stock Symbol ---
        symbol = request.form.get("symbol")
        # check if stock symbol was not entered
        if not symbol:
            return apology("Please enter a Stock symbol")

        # lookup returns a dictionary including name, price, symbol
        stock = lookup(symbol)
        # check if stock symbol exists
        if not stock:
            return apology("Stock symbol does not exist")
        if not request.form.get("shares"):
            return apology("shares cannot be blank")
        # if int(request.form.get("shares")) != float(request.form.get("shares")):
        #     return apology("shares cannot be in decimal", 400)
        # if int(request.form.get("shares")) < 1:
        #     return apology("shares cannot be less than 1", 400)
        if not request.form.get("shares").isnumeric():
            return apology("shares cannot be in decimal", 400)

        # --- Buy stock ---
        userbalance = (db.execute("SELECT cash FROM users WHERE id=?", session["user_id"]))[0]["cash"]
        # determine unit price
        unitprice = float(stock["price"])
        # number of units wanted
        shares = int(request.form.get("shares"))
        # total cost
        total = unitprice * int(shares)

        if userbalance < total:
            return apology("U Broke")
        else:
            ownedstocks = db.execute("SELECT symbol, shares FROM transactions WHERE user_id=? AND symbol LIKE ?", session["user_id"], symbol)
            db.execute("UPDATE users SET cash=? WHERE id=?", userbalance - total, session["user_id"])
            # check if user already owns this stock (if yes, update stock)
            if not ownedstocks:
                db.execute("INSERT INTO transactions(user_id, symbol, unit_cost, shares, total_cost, second, minute, hour, day, month, year) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", session["user_id"], stock["symbol"], stock["price"], shares, total, second, minute, hour, day, month, year)
                db.execute("INSERT INTO history(user_id, symbol, unit_cost, shares, total_cost, second, minute, hour, day, month, year, status) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", session["user_id"], stock["symbol"], stock["price"], shares, total, second, minute, hour, day, month, year, 0)
            else:
                prevq = db.execute("SELECT shares FROM transactions WHERE user_id= ? AND symbol LIKE ?", session["user_id"], symbol)[0]["shares"]
                db.execute("UPDATE transactions SET shares = ? WHERE user_id=? AND symbol LIKE ?", prevq + shares, session["user_id"], symbol)
            return redirect("/")

    # display form to user to buy stock
    else:
        return render_template("buystock.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    data = db.execute("SELECT * FROM history WHERE user_id=?", session["user_id"])
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
        rows = db.execute("SELECT * FROM users WHERE username=?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # CORRECT USERNAME & PASSWORD

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
    """Get stock quote."""

    # lookup the stock symbol & display results
    if request.method == "POST":
        symbol = request.form.get("symbol")
        # check if stock symbol was not entered
        if not symbol:
            return apology("Please enter a Stock symbol")

        # lookup returns a dictionary including name, price, symbol
        stock = lookup(symbol)
        # check if stock symbol exists
        if not stock:
            return apology("Stock symbol does not exist")

        # means it is a valid stock symbol --> display stock in stock.html
        price = usd(stock["price"])
        return render_template("stock.html", stock=stock, price=price)


    # else it was a get request --> display form to allow user to request quote/price of a specific stock
    else:
        return render_template("quote_search.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # get the registration form for user
    if request.method == "GET":
        return render_template("register.html")

    # else request.method == "POST" --> meaning we have received inputs and need to validate them
    usernamesDicts = db.execute("SELECT username FROM users")
    usernames=[]
    for u in usernamesDicts:
        usernames.append(u["username"])

    username = request.form.get("username")
    password = request.form.get("password")
    confirmation = request.form.get("confirmation")

    # check if username already exists
    if username in usernames:
        return apology("Username already exists")

    # check if password is not same as confirmation
    elif password != confirmation:
        return apology("Passwords don't match")

    # check if empty
    elif not username:
        return apology("Username cannot be blank")
    elif not password:
        return apology("Password cannot be blank")
    elif not confirmation:
        return apology("Confirmation cannot be blank")


    # if survives all checks, then insert
    db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, generate_password_hash(password, method='pbkdf2:sha256', salt_length=8))
    session["user_id"] = int(db.execute("SELECT id FROM users WHERE username=?", username)[0]["id"])
    return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # check if user has this stock and then sell  it
    if request.method == "POST":
        x = datetime.datetime.now()
        second = x.second
        minute = x.minute
        hour = x.hour
        day = x.day
        month = x.month
        year = x.year


        # --- VALIDATE Stock Symbol ---
        symbol = request.form.get("symbol")
        # check if stock symbol was not entered
        if not symbol:
            return apology("Please enter a Stock symbol")

        # lookup returns a dictionary including name, price, symbol
        thisstock = lookup(symbol)
        # check if stock symbol exists
        if not thisstock:
            return apology("Stock symbol does not exist")
        shares = int(request.form.get("shares"))
        if not shares:
            return apology("shares cannot be blank")

        # --- END VALIDATE Stock Symbol ---

        user = db.execute("SELECT * FROM users WHERE id=?", session["user_id"])[0]
        # check if user owns stock
        userstocks = db.execute("SELECT * FROM transactions WHERE user_id=? AND symbol LIKE ?", session["user_id"], symbol)
        if not userstocks:
            return apology("You don't own this stock")
        # check if number of stocks owned >= num of stocks selling
        if shares > userstocks[0]["shares"]:
            return apology("You don't own have this many shares")

        # add to user's cash the total_cost of these stocks
        balance = user["cash"] + (userstocks[0]["unit_cost"] * shares)
        db.execute("INSERT INTO history(user_id, symbol, unit_cost, shares, total_cost, second, minute, hour, day, month, year, status) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", session["user_id"], userstocks[0]["symbol"], thisstock["price"], shares, balance, second, minute, hour, day, month, year, 1)
        db.execute("UPDATE users SET cash=? WHERE id=?", balance, session["user_id"])
        # delete these stocks from user (if all shares are sold OR some shares are sold)
        if shares == userstocks[0]["shares"]:
            db.execute("DELETE FROM transactions WHERE symbol LIKE ?", symbol)
            return redirect("/")
        # else some shares are sold
        else:
            db.execute("UPDATE transactions SET shares=? WHERE symbol LIKE ?", userstocks[0]["shares"] - shares, symbol)
            return redirect("/")
    else:
        userstocksDictsList = db.execute("SELECT symbol FROM transactions WHERE user_id=?", session["user_id"])
        userstockssymbols=[]
        for us in userstocksDictsList:
            userstockssymbols.append(us["symbol"])
        return render_template("sellstock.html", userstockssymbols=userstockssymbols)