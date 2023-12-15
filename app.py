from flask import Flask, render_template, request, redirect
import psycopg2
import pandas as pd
from io import StringIO
import sys
from sqlalchemy import create_engine
import urllib.parse
import sweetviz as sv
from typing import Dict

#Trying to fix Sweetviz in a web-based app:
from multiprocessing import Process
import matplotlib
matplotlib.use('Agg')

app = Flask(__name__, template_folder='templates')
db_config:Dict[str,str]

#Function to connect to the db,
#Needs handler for errors
def connect():
    global db_config
    print(f"Inside connect Function")
    conn = psycopg2.connect(**db_config) 
        
    return conn      

# Function to create a SQLAlchemy engine
#Both pd.read_sql or pd.read_sql_query method expects a SQLAlchemy connectable (engine/connection) or database string URI or sqlite3 DBAPI2 connection.
def create_engine_from_conn(conn):
    #if there is no special character use this:
    #dsn = f"postgresql://{conn.info.user}:{conn.info.password}@{conn.info.host}:{conn.info.port}/{conn.info.dbname}"
        
    #if you have special character in db_config use this.
    user = urllib.parse.quote_plus(conn.info.user)
    password = urllib.parse.quote_plus(conn.info.password)
    host = urllib.parse.quote_plus(conn.info.host)
    dbname = urllib.parse.quote_plus(conn.info.dbname)
    dsn = f"postgresql://{user}:{password}@{host}:{conn.info.port}/{dbname}"
    return create_engine(dsn)

#Function to run a query
def run_query(cursor, query):
    cursor.execute(query)
    return cursor.fetchall()   

def run_query_no_fetch(cursor, query):
    cursor.execute(query)

def generate_sweetviz_report(df):
    report = sv.analyze(df)
    report.show_html(open_browser=True)


@app.route('/')
def dbsetup():
    return render_template('dbsetup.html')

@app.route('/error')
def error():
    e=''
    return render_template('erro.html', error_message=str(e))

@app.route('/connectdb', methods=['POST'])
def connectdb():
    global db_config
    try:
        if request.method == 'POST':
            host = request.form['host']
            port = request.form['port']
            database = request.form['database']
            user = request.form['user']
            pwrd = request.form['pwrd']


        db_config = {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': pwrd
        }
        
        # Call function to connect to db based on form
        conn = connect()
        cursor = conn.cursor()
        cursor.close()
        conn.close()

        # Directly call the index function to fetch records and render the template
        return index()
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return render_template('erro.html', error_message=str(e))

# Rota para exibir os registros da tabela
@app.route('/index', methods=['GET'])
def index():
    try:
        with connect().cursor() as cursor:
            #Metada Query
            query = '''SELECT
                        table_schema,
                        table_name,
                        column_count,
                        pg_total_relation_size((table_schema || '.' || table_name)::regclass) AS total_size,
                        pg_size_pretty(pg_total_relation_size((table_schema || '.' || table_name)::regclass)) AS total_size_pretty
                    FROM (
                        SELECT
                            table_schema,
                            table_name,
                            count(column_name) AS column_count
                        FROM information_schema.columns
                        WHERE table_schema NOT LIKE 'pg_%' AND table_schema != 'information_schema'
                        GROUP BY table_schema, table_name
                    ) AS table_info
                    ORDER BY table_schema, table_name;'''
            records = run_query(cursor, query)       
        return render_template('index.html', records=records)
    
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return render_template('erro.html', error_message=str(e))

@app.route('/details/<string:schemaname>/<string:tablename>')
def details(schemaname, tablename):
    try:
        with connect() as conn:
            #Get Full Content of tablename
            query = f'''
                    SELECT * from {schemaname}.{tablename};
                    '''
            
            # Transform full content into df to run pandas functions
            engine = create_engine_from_conn(conn)        
            df = pd.read_sql(query, con=engine)
            engine.dispose()


            head_df = df.head()
            tail_df = df.tail()

            # Describe
            desc_df = df.describe(include='all')

            # Redirect stdout to capture the output of df.info()
            original_stdout = sys.stdout
            sys.stdout = StringIO()
            df.info()
            # Get the captured output as a string
            info_output = sys.stdout.getvalue()
            # Restore the original stdout
            sys.stdout = original_stdout

            # Redirect stdout to capture the output of df.isnull().sum()
            original_stdout = sys.stdout
            sys.stdout = StringIO()
            df.isnull().sum()
            # Get the captured output as a string
            isnull_sum_output = sys.stdout.getvalue()
            # Restore the original stdout
            sys.stdout = original_stdout

            print(isnull_sum_output)
        return render_template('details.html', data=df, head_df=head_df, tail_df=tail_df, info_output=info_output, desc_df=desc_df, isnull_sum_output=isnull_sum_output)
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return render_template('erro.html', error_message=str(e))


# Rota para adicionar um novo registro
@app.route('/insert/<string:schemaname>/<string:tablename>')    
def insert(schemaname, tablename):      
    try:
        with connect() as conn:
            query = f'''
                    SELECT * from {schemaname}.{tablename};
                    '''

            # Transform full content into df to run pandas functions
            engine = create_engine_from_conn(conn)
            df = pd.read_sql(query, con=engine)
            engine.dispose()

            return render_template('insert.html', data=df, schemaname=schemaname, tablename = tablename)    
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return render_template('erro.html', error_message=str(e))
    
@app.route('/insertOp/<string:schemaname>/<string:tablename>', methods=['POST'])
def insertOp(schemaname, tablename):
    try:   
        if request.method == 'POST':
            values = request.form['values']
        
        with connect() as conn:
            with connect().cursor() as cursor:
                query = f''' 
                        INSERT INTO {schemaname}.{tablename} VALUES ({values})
                        '''
                run_query_no_fetch(cursor, query)


        return index()
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return render_template('erro.html', error_message=str(e))


@app.route('/mainsweetvizpage/<string:schemaname>/<string:tablename>')
def mainsweetvizpage(schemaname, tablename):
    try:
        return render_template('showreport.html', schemaname=schemaname, tablename=tablename)
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return render_template('erro.html', error_message=str(e))

@app.route('/show_sv/<string:schemaname>/<string:tablename>')
def show_sv(schemaname, tablename):
    try:
        with connect() as conn:
            query = f'''SELECT * FROM {schemaname}.{tablename}'''
            
            engine = create_engine_from_conn(conn)
            df = pd.read_sql(query, con=engine)
            engine.dispose()

            p = Process(target=generate_sweetviz_report, args=(df,))
            p.start() 
            p.join()

        return mainsweetvizpage(schemaname=schemaname, tablename=tablename)
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return render_template('erro.html', error_message=str(e))

@app.errorhandler(405)
def method_not_allowed_error(e):
    error_message = "Método não permitido para a URL solicitada."
    return render_template('erro.html', error_message=error_message, error_code=405), 405

@app.errorhandler(404)
def page_not_found_error(e):
    error_message = "Página não encontrada."
    return render_template('erro.html', error_message=error_message, error_code=404), 404

if __name__ == '__main__':
    app.run(debug=True)
