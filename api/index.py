from dotenv import load_dotenv
from flask import Flask, jsonify, Response, request
from flask_cors import CORS
import pandas as pd
import os
from dependencies.vanna import VannaDefault
from vanna.ollama import Ollama
from vanna.chromadb import ChromaDB_VectorStore
import psycopg2
import pandas as pd

import sys

load_dotenv()
app = Flask(__name__, static_url_path="")
CORS(app, resources={r"/api/*": {"origins": "*"}})

# VANNA INITIALIZATION
# vannakey = os.environ.get("VANNA_API_KEY")
# account = os.environ.get("SNOWFLAKE_ACCOUNT")
# username = os.environ.get("SNOWFLAKE_USERNAME")
# password = os.environ.get("SNOWFLAKE_PASSWORD")
# database = os.environ.get("SNOWFLAKE_DATABASE")
# role = os.environ.get("SNOWFLAKE_ROLE")
# model = os.environ.get("VANNA_MODEL")
# vn = VannaDefault(model=model, api_key=vannakey)
# vn.connect_to_snowflake(
#     account=account, username=username, password=password, database=database, role=role
# )

class MyVanna(ChromaDB_VectorStore, Ollama):
    def __init__(self, config=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        Ollama.__init__(self, config=config)

vn = MyVanna(config={'model': 'llama3.2-vision'})
vn.connect_to_postgres(host='10.10.10.168', dbname='postgres', user='admin', password='admin', port='5432')

def run_sql(sql: str) -> pd.DataFrame:
    with psycopg2.connect(
        host='10.10.10.168',
        database='postgres',
        user='admin',
        password='admin',
        port='5432'
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            result = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            df = pd.DataFrame(result, columns=columns)
            return df
vn.run_sql = run_sql
vn.run_sql_is_set = True
database = "postgres"

@app.route("/api/v1/generate_questions", methods=["GET"])
def generate_questions():
    print({database})
    return jsonify(
        {
            "type": "question_list",
            "questions": vn.generate_questions(),
            "header": "Here are some questions you can ask:",
        }
    )

@app.route("/api/v1/generate_sql", methods=["GET"])
def generate_sql():
    question = request.args.get("question")
    if question is None:
        return jsonify({"type": "error", "error": "No question provided"})
    sql = vn.generate_sql(question=question)
    return jsonify({"type": "sql", "text": sql})


@app.route("/api/v1/run_sql", methods=["POST"])
def run_sql():
    data = request.get_json()
    sql = data.get("sql") if data else None
    print("sql", sql)
    if sql is None:
        return jsonify({"type": "error", "error": "No SQL query provided", "sql": sql})
    try:
        df = vn.run_sql(sql=sql)
        return jsonify({"type": "df", "df": df.head(10).to_json(orient="records")})
    except Exception as e:
        return jsonify({"type": "error", "error": str(e)})


@app.route("/api/v1/download_csv", methods=["POST"])
def download_csv():
    data = request.get_json()
    df_json = data.get("df")
    if df_json is None:
        return jsonify({"type": "error", "error": "No DataFrame provided"})
    df = pd.read_json(df_json, orient="records")
    csv = df.to_csv(index=False)
    return Response(
        csv,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=data.csv"},
    )


@app.route("/api/v1/get_training_data", methods=["GET"])
def get_training_data():
    df = vn.get_training_data()

    print(df, file=sys.stderr)
    return jsonify(
        {
            "type": "df",
            "id": "training_data",
            "df": df.head(25).to_json(orient="records"),
        }
    )


@app.route("/api/v1/remove_training_data", methods=["POST"])
def remove_training_data():
    data = request.get_json()
    new_id = data.get("id")
    if new_id is None:
        return jsonify({"type": "error", "error": "No id provided"})
    # Placeholder logic, replace with actual call to remove training data
    if vn.remove_training_data(id=new_id):
        return jsonify({"success": True})
    else:
        return jsonify({"type": "error", "error": "Couldn't remove training data"})


@app.route("/api/v1/train", methods=["POST"])
def add_training_data():
    data = request.get_json()
    question = data.get("question")
    sql = data.get("sql")
    ddl = data.get("ddl")
    documentation = data.get("documentation")
    try:
        new_id = vn.train(
            question=question, sql=sql, ddl=ddl, documentation=documentation
        )
        return jsonify({"id": new_id})
    except Exception as e:
        return jsonify({"type": "error", "error": str(e)})


if __name__ == "__main__":
    app.run(debug=True)
