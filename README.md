# Large Language Models Enhanced Automatic Knowledge Graphs Generation

## Application
Steps to run the application:

1. Activate a virtual environment
`
sudo apt install python3.8-venv
`

`
python3 -m venv venv
`

`
source venv/bin/activate
`

2. Navigate to the app script:
`
cd app/to_kg_app
`

3. Install requirements 
`
pip3 install -r requirements.txt
`

4. Start the application
`
streamlit run to_kg_app.py
`

In order to generate a knowledge graph from text you need to have an OpenAI API key. 

## Scripts
Steps to start the script:

1. Activate a virtual environment
`
sudo apt install python3.8-venv
`

`
python3 -m venv venv
`

`
source venv/bin/activate
`

2. Navigate to the scripts directory:
`
cd scripts
`

### Generate a KG from an input text 

1. Navigate to the textToKG directory
`
cd textToKG/
`

2. Install requirements 
`
pip3 install -r requirements.txt
`

3. Run the script by providing your Open AI API key as the first parameter
`
python ./textToKG/toKG.py <YOUR_API_KEY> <input_dir.txt> <output_dir.ttl>
`


### Run a deduplication of your KG 
1. Navigate to the deduplication directory
`
cd deduplication/
`

2. Install requirements 
`
pip3 install -r requirements.txt
`

3. Run the deduplication script.  
`
python ./deduplication.py <input_file.ttl> <output_file.ttl>
`

The deduplication step requires user interaction. It is based on python's dedupe library (https://docs.dedupe.io/en/latest/). After running the script you will receive multiple questions about deduplicated statements in your knowledge graph. 


## License 
CC BY-SA 4.0
CC-BY-SA cite as:  Vasil Vasilev, Georgi Grazhdanski, Sylvia Vassileva, Ivan Koychev and Svetla Boytcheva. (2024) Large language models enhanced automatic knowledge graphs generation in medical domain. It was submitted to ESWC 2024