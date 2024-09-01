import argparse
import subprocess
import os

def run_python_script(script_path, dbname, user, password, host, port):
    """Runs the Python insert script with database credentials as arguments."""
    try:
        # Run the Python script as a subprocess
        subprocess.run(['python', script_path, '--dbname', dbname, '--user', user,
                        '--password', password, '--host', host, '--port', port], check=True)
        print("Python insert script executed successfully.")
    
    except subprocess.CalledProcessError as error:
        print(f"Error executing the Python script: {error}")


def run_pg_dump(local_dbname, user, password, host, port, live_db_url, table_name):
    """Dumps specific table data from the local database and restores it to the external live database after truncating the target table."""
    try:
        # Set up the environment variable for the password
        os.environ['PGPASSWORD'] = password

        # Step 1: Dump data from the public.poem_words in the local database
        dump_command = (
            f"pg_dump --host={host} --port={port} --username={user} --dbname={local_dbname} "
            f"--data-only --table={table_name}"
        )

        # Step 2: Truncate the table in the live database
        truncate_command = (
            f"psql {live_db_url} -c \"TRUNCATE TABLE {table_name} CASCADE;\""
        )

        # Step 3: Restore the data to the live database
        restore_command = f"psql {live_db_url}"

        # Print the commands for debugging purposes
        print(f"Running command: {dump_command} | {truncate_command} | {restore_command}")

        # Execute the truncate command first
        subprocess.run(truncate_command, shell=True, check=True)

        # Execute the dump and restore commands
        with subprocess.Popen(dump_command, shell=True, stdout=subprocess.PIPE) as dump_proc:
            with subprocess.Popen(restore_command, shell=True, stdin=dump_proc.stdout) as restore_proc:
                restore_proc.communicate()  # Wait for the restore process to complete

        print(f"Table {table_name} successfully dumped and restored to the live database.")

    except subprocess.CalledProcessError as error:
        print(f"Error during pg_dump or restore: {error}")
    finally:
        # Remove the password from the environment variables
        del os.environ['PGPASSWORD']


def copy_to_aws():
    # Argument parser
    parser = argparse.ArgumentParser(description="Migrate local PostgreSQL database to external live database.")
    
    # PostgreSQL credentials for local database
    parser.add_argument('--local_dbname', required=True, help="Local database name")
    parser.add_argument('--user', required=True, help="Database user")
    parser.add_argument('--password', required=True, help="Database password")
    parser.add_argument('--host', default='localhost', help="Database host (default: localhost)")
    parser.add_argument('--port', default='5432', help="Database port (default: 5432)")
    
    # Path to the Python insert script
    parser.add_argument('--script_path', required=True, help="Path to the Python insert script")
    
    # Live database URL
    parser.add_argument('--live_db_url', required=True, help="URL of the external live database")


    # Parse arguments
    args = parser.parse_args()

    # Run the Python insert script on the local database
    run_python_script(args.script_path, args.local_dbname, args.user, args.password, args.host, args.port)

    # Dump the specific tables and restore them to the live database: public.poems_poem, public.poem_words, public.poems_word
    run_pg_dump(args.local_dbname, args.user, args.password, args.host, args.port, args.live_db_url, 'public.poems_poem')
    run_pg_dump(args.local_dbname, args.user, args.password, args.host, args.port, args.live_db_url, 'public.poems_word')
    run_pg_dump(args.local_dbname, args.user, args.password, args.host, args.port, args.live_db_url, 'public.poems_poem_words')
    
    
if __name__ == "__main__":
    copy_to_aws()
  

