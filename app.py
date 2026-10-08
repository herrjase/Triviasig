from flask import Flask, render_template
app = Flask(__name__)
@app.route("/")
def index():
    return render_template("index.html")
@app.route("/profile")
def profile():
    return render_template("profile.html")
@app.route("/army")
def army():
    return render_template("army.html")
@app.route("/regions")
def regions():
    return render_template("regions.html")
@app.route("/mercenaries")
def mercenaries():
    return render_template("mercenaries.html")
@app.route("/history")
def history():
    return render_template("history.html")
@app.route("/rating")
def rating():
    return render_template("rating.html")
@app.route("/settings")
def settings():
    return render_template("settings.html")
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
