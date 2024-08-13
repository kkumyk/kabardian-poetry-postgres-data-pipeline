import time
import os
from dotenv import load_dotenv
import psycopg2
import requests
from lxml import html
from bs4 import BeautifulSoup
import pandas as pd
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)

# will search for .env file in local folder and load variables
load_dotenv() 

# wait for the database to be ready
time.sleep(10)

conn_params = {
    'dbname':os.getenv('DB_NAME'), 
    'user':os.getenv('DB_USER'),
    'password':os.getenv('DB_PASSWORD'), 
    'host':os.getenv('DB_HOST') 
}
    
# initialize conn and cur to None
conn = None
cur = None

# connect to the database
try:
    conn = psycopg2.connect(**conn_params)
    cur = conn.cursor()
    
    # create table if it doesn't exist
    cur.execute('''
    CREATE TABLE IF NOT EXISTS poems_poem (
        id SERIAL PRIMARY KEY,
        title TEXT,
        author TEXT,
        contents TEXT NOT NULL,
        UNIQUE (title, author)
    );
    ''')
    conn.commit()

    cur.execute('''
    CREATE TABLE IF NOT EXISTS poems_word (
        id SERIAL PRIMARY KEY,
        word TEXT NOT NULL UNIQUE,
        eng_transl TEXT NOT NULL,
        rus_transl TEXT NOT NULL
    );
    ''')
    conn.commit()

    cur.execute('''
    CREATE TABLE IF NOT EXISTS poems_poem_words (
        id SERIAL PRIMARY KEY,
        poem_id INTEGER NOT NULL,
        word_id INTEGER NOT NULL,
        FOREIGN KEY (poem_id) REFERENCES poems_poem(id) ON DELETE CASCADE,
        FOREIGN KEY (word_id) REFERENCES poems_word(id) ON DELETE CASCADE,
        UNIQUE (poem_id, word_id)
    );
    ''')
    conn.commit()
    
    
    poem_file_path = 'poems/poem.txt'
    poem_id = None # the ID of the poem being processed
    
    def insert_poem(poem_file):

        with open(poem_file, 'r') as file:
            lines = file.readlines()

        poem_contents = {"author":"", "title": "", "contents":""}
        poem_contents["author"] = lines[0].rstrip() # extract the author from the poem.txt file
        poem_contents["title"] = lines[1].rstrip() # extract the title from the poem.txt file

        text = ""
        for line in lines[2:]:
            text += line.rstrip() + "<br/>"    
        poem_contents["contents"] = text.replace("<br/><br/>","<br/>").rsplit('<',1)[0] # extract the poem itself from the poem.txt file

        title = poem_contents["title"]
        author = poem_contents["author"]
        contents = poem_contents["contents"]
        poem_to_insert = (title, author, contents)
        
        return poem_to_insert
    
    insert_poem_query = '''
        INSERT INTO poems_poem (title, author, contents)
        VALUES  (%s,%s,%s)
        ON CONFLICT (title, author) DO NOTHING
        RETURNING id;
    '''
    cur.execute(insert_poem_query, insert_poem(poem_file_path))
    
    # check if cur.fetchone() returns a result   
    result = cur.fetchone()
    if result:
        poem_id = result[0]
    else:
        raise Exception("No new poem was inserted, it might already exist in the database. Execution stopped.")

    
    conn.commit()
    
    
    # fetch and print the data
    cur.execute('SELECT * FROM poems_poem;')
    rows = cur.fetchall()
    for row in rows:
        print(row)
        
    
    def process_text_file(file_path):
        with open(file_path, 'r') as file:
            content = file.read()
            
        content = content.lower()
        words = content.split()
        
        seen = set() # remove duplicate words while preserving order
        unique_words = []
        for word in words:
            if word not in seen:
                seen.add(word)
                unique_words.append(word)
                
        word_urls = ["https://kbd.wiktionary.org/wiki/" + word for word in unique_words]
        return word_urls
    
    # print(process_text_file(poem_file_path))
    
    def check_urls_and_extract_word_meta(urls):
        results = []
        for url in urls:
            try:
                response = requests.get(url)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    h1_tag = soup.find('h1')
                    
                    if len(h1_tag.get_text()) > 2:
                        tree = html.fromstring(response.content)
                        eng_translation = tree.xpath('//h5[.="ИНДЖЫЛЫБЗЭ"]/following::ul[1]/li/text()')[0].split(":")[1].strip()
                        rus_translation = tree.xpath('//h5[.="УРЫСЫБЗЭ"]/following::ul[1]/li/text()')[0].split(":")[1].strip()
                        
                        print(eng_translation, rus_translation)
                        results.append({
                            'word': h1_tag.get_text(),
                            "eng_transl": eng_translation.replace("'", "\"").replace('"', '\"'),
                            "rus_transl": rus_translation.replace("'", "\"").replace('"', '\"'),
                        })
                        
            except requests.RequestException as e:
                results.append({url: f"Request failed: {e}"})
        return results


    def add_new_words_to_word_pool(poem_file_path, poem_id):
        word_urls = process_text_file(poem_file_path)
        
        # array of objects with word, eng and rus translations
        extracted_contents = check_urls_and_extract_word_meta(word_urls)
        print(extracted_contents)
        
        words_to_insert = []
        
        '''
        create a hash map for mapping poem id to word ids found in that poem
        the code should check if the words that had been found in the poem was previously added to the word pool
        if the above is the case, the existing word id should be allocated to the poem
        if not, a newly allocated word id should be added
        ''' 
        word_to_id_map = {}
        
        for word_obj in extracted_contents:
            word = word_obj["word"]
            eng_transl = word_obj["eng_transl"]
            rus_transl = word_obj["rus_transl"]
            
            # check if the word already exists in the words pool table
            cur.execute('SELECT id FROM poems_word WHERE word = %s', (word,))
            word_id_result = cur.fetchone()
            
            if word_id_result:
                word_id = word_id_result[0]
            else:
                # insert the new word and get its id TODO
                cur.execute('INSERT INTO poems_word (word, eng_transl, rus_transl) VALUES (%s, %s, %s) RETURNING id', (word, eng_transl, rus_transl))
                word_id = cur.fetchone()[0]
            
            word_to_id_map[word] = word_id
            
            words_to_insert.append((word, eng_transl, rus_transl))
        print(words_to_insert)
        
        # insert into poems_poem_words table
        poems_poem_words_to_insert = [(poem_id, word_to_id_map[word_obj["word"]]) for word_obj in extracted_contents]
        
        return words_to_insert, poems_poem_words_to_insert
    
    
    words_to_insert, poems_poem_words_to_insert = add_new_words_to_word_pool(poem_file_path, poem_id)
        
    insert_words_query = 'INSERT INTO poems_word (word, eng_transl, rus_transl) VALUES (%s,%s,%s) ON CONFLICT (word) DO NOTHING;'
    cur.executemany(insert_words_query, words_to_insert)
    conn.commit()
    
    insert_poems_poem_words_query = 'INSERT INTO poems_poem_words (poem_id, word_id) VALUES (%s, %s) ON CONFLICT DO NOTHING'
    cur.executemany(insert_poems_poem_words_query, poems_poem_words_to_insert)
    conn.commit()
    
    cur.close()
    conn.close()
        

except Exception as e:
    print(f"An error occurred: {e}")
finally:
    if cur:
        cur.close()
    if conn:
        conn.close()