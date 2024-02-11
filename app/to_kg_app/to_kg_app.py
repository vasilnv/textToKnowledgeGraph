import streamlit as st
from openai import OpenAI
import re
from rdflib import Graph
from rdflib.extras.external_graph_libs import rdflib_to_networkx_multidigraph
from rdflib.plugins.parsers.notation3 import BadSyntax
from pyvis.network import Network
import streamlit.components.v1 as components

st.title('Convert Text to Knowledge Graph')

openai_api_key = st.sidebar.text_input('OpenAI API Key', type='password')

def extract_ttl_content_gpt_3(text):
    ttl_pattern = r'```turtle\n([\s\S]*?)\n```'
    matches = re.search(ttl_pattern, text)
    return matches.group(1) if matches else None


def get_system_prompt():
    return f"""Use the context of medicine. Translate the following user text to an RDF graph using the SCHEMA.ORG ontology formatted as TTL. Use only valid entities (such as schema:MedicalCondition, schema:MedicalSignOrSymptom, schema:MedicalTest, schema:Drug) and properties (such as schema:possibleTreatment, schema:causeOf, schema:signOrSymptom, schema:usedToDiagnose, schema:drug, schema:possibleComplication, schema:guideline) listed on SCHEMA.ORG.
Not allowed relations: schema:indication, schema:indicates, schema:indications, schema:indicate, schema:partOf , schema:prevalence, schema:cause , schema:outcome, schema:subProcedure, schema:isA, schema:complication.

Use the prefix ex: with IRI <http://example.com/> for any created entities or properties."""


def get_ontology_1(system_prompt, protocol, temp):
    client = OpenAI(api_key=openai_api_key)
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": protocol,
            }
        ],
        model="gpt-3.5-turbo-0125",
        temperature=temp

    )
    return chat_completion.choices[0].message.content

def convert_text_to_kg(text):
    chunk_size = 2000
    chunks = []
    curr_chunk_size = 0
    curr_chunk = ""
    for line in text.splitlines():
        if curr_chunk_size > chunk_size:
            chunks.append(curr_chunk)
            curr_chunk = ""
            curr_chunk_size = 0
        curr_chunk += line
        curr_chunk += "\n"
        curr_chunk_size += len(line)
    chunks.append(curr_chunk)

    args = {
        'temperature': 0.35,
        'max_new_tokens': 2048,
        # 'protocols_dir': '/content/drive/MyDrive/Thesis/week0/protocols/MI/protocol',
        # 'output_dir': '/content/drive/MyDrive/Thesis/week1/results/gpt-4-turbo/MI'
    }

    print('Prompting the LLM...')
    g = Graph()
    ttl_output_whole = ""
    for chunk in chunks:
        print(f'chunk is {chunk}')
        model_ontology_output = get_ontology_1(get_system_prompt(), chunk, args['temperature'])
        print(f"OUTPUT FROM LLM: {model_ontology_output}")
        ttl_output = extract_ttl_content_gpt_3(model_ontology_output)
        print(f"EXTRACTED: {ttl_output}")
        if len(ttl_output) != 0:
            ttl_output_whole += ttl_output
        # # merging
            try:
                g1 = Graph()
                g1.parse(data=ttl_output, format='ttl')
                g += g1
            except BadSyntax:
                print(f"Error in Turtle syntax")

    print(f'Writing the result {ttl_output_whole}')
    # st.code(ttl_output_whole)
    could_download = len(ttl_output_whole) == 0

    # st.download_button(label="Download file", data=ttl_output_whole, disabled=could_download)

    G = rdflib_to_networkx_multidigraph(g)
    nt = Network('500px', '500px')
    nt.from_nx(G)

    try:
        path = '/tmp'
        nt.show_buttons()
        nt.save_graph(f'{path}/pyvis_graph.html')
        HtmlFile = open(f'{path}/pyvis_graph.html', 'r', encoding='utf-8')
    # Save and read graph as HTML file (locally)
    except:
        path = '/html_files'
        nt.show_buttons()
        nt.save_graph(f'{path}/pyvis_graph.html')
        HtmlFile = open(f'{path}/pyvis_graph.html', 'r', encoding='utf-8')

    # Load HTML file in HTML component for display on Streamlit page
    components.html(HtmlFile.read(), height=435)
    return ttl_output_whole

def generate_response(input_text):
    # llm = OpenAI(temperature=0.7, openai_api_key=openai_api_key)
    ttl_file = convert_text_to_kg(input_text)
    st.code(ttl_file)
    return ttl_file

with st.form('text_form'):
    text = st.text_area('Enter text:')
    submitted = st.form_submit_button('Submit')
    if not openai_api_key.startswith('sk-'):
        st.warning('Please enter your OpenAI API key!', icon='⚠')
    if submitted and openai_api_key.startswith('sk-'):
        st.session_state.submitted = True
        if 'submitted' in st.session_state:
            data_to_download = generate_response(text)

if submitted:
    st.download_button(label='Download', data=data_to_download, file_name='kg.ttl')
