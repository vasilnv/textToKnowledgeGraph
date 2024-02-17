import streamlit as st
from openai import OpenAI
import re
from rdflib import Graph
from rdflib.plugins.parsers.notation3 import BadSyntax
from streamlit_agraph import agraph, Node, Edge, Config
import os
import csv

st.title('Convert Text to Knowledge Graph')

openai_api_key = st.sidebar.text_input('OpenAI API Key', type='password')
modelGpt = "gpt-3.5-turbo-0125"


def extract_ttl_content_gpt_3(text):
    ttl_pattern = r'```turtle\n([\s\S]*?)\n```'
    matches = re.search(ttl_pattern, text)
    return matches.group(1) if matches else None


def get_system_prompt():
    return f"""Use the context of medicine. Translate the following user text to an RDF graph using the SCHEMA.ORG ontology formatted as TTL. Use only valid entities (such as schema:MedicalCondition, schema:MedicalSignOrSymptom, schema:MedicalTest, schema:Drug) and properties (such as schema:possibleTreatment, schema:causeOf, schema:signOrSymptom, schema:usedToDiagnose, schema:drug, schema:possibleComplication, schema:guideline) listed on SCHEMA.ORG.
Not allowed relations: schema:indication, schema:indicates, schema:indications, schema:indicate, schema:partOf , schema:prevalence, schema:cause , schema:outcome, schema:subProcedure, schema:isA, schema:complication.

Use the prefix ex: with IRI <http://example.com/> for any created entities or properties."""


def get_missed_statements_prompt():
    return f"""Now you have the opportunity to go through each sentence in the medical text again and update the statements from the ontology. Make sure the ontology explicitly states every statement from the text. Add any missed statements. Use only information from the medical text. Output the full result ontology"""


def get_single_entities_prompt():
    return f"""Now go through the result ontology and make sure each created entity defines a single object. Check if there are Literals and string objects that can be represented with a single entity. Update the statements in the ontology where possible. Use prefix ex: with IRI <http://example.com/> for any created entities. Do not lose any knowledge in the new ontology. """


def format_single_part_conversation(role, message):
    return {
        'role': role,
        'content': message
    }


def format_initial_messages(system_prompt, protocol):
    return [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": protocol
        }
    ]


def get_ontology(client1, temp, prompt_messages):
    client = OpenAI(api_key=openai_api_key)
    chat_completion = client.chat.completions.create(
        messages=prompt_messages,
        model="gpt-3.5-turbo-0125",
        temperature=temp,
        max_tokens=4096,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0

    )
    return chat_completion.choices[0].message.content


def load_valid_properties():
    current_file_path = os.path.dirname(os.path.abspath(__file__))
    valid_props_file = os.path.join(current_file_path, 'validProperties.csv')

    with open(valid_props_file, 'r') as f:
        reader = csv.reader(f)
        valid_props = {rows[0]: rows[1] for rows in reader}

    return valid_props


def post_process_ttl_file(g, valid_props):
    for s, p, o in g:
        predicate_suffix = p.split("#")[-1]
        if predicate_suffix in valid_props:
            g.remove((s, p, o))
            new_predicate = f"{p.split('#')[0]}#{valid_props[predicate_suffix]}"
            g.add((s, new_predicate, o))
    result_ontology = g.serialize(format="turtle")
    print(f"result ontology: {result_ontology}")
    print(f"serialized result ontology: {g.serialize(format='ttl')}")
    return result_ontology


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
    client = OpenAI(api_key=openai_api_key)
    g = Graph()
    ttl_output_whole = ""
    for chunk in chunks:
        messages = format_initial_messages(get_system_prompt(), chunk)
        model_ontology_output = get_ontology(client, args['temperature'],
                                             messages)
        print("Finished first step of the pipeline")
        messages.append(format_single_part_conversation('assistant', model_ontology_output))
        messages.append(format_single_part_conversation('user', get_missed_statements_prompt()))
        final_ontology = get_ontology(client, args['temperature'], messages)
        print("Finished second step of the pipeline")
        print("Extracting file in turtle format...")
        ttl_output = extract_ttl_content_gpt_3(final_ontology)

        print("Merging chunks...")
        if len(ttl_output) != 0:
            ttl_output_whole += ttl_output
        # merging
            try:
                g1 = Graph()
                g1.parse(data=ttl_output, format='ttl')
                g += g1
            except BadSyntax:
                print(f"Error in Turtle syntax")

    valid_properties = load_valid_properties()
    print("Post-processing the result ontology...")
    ttl_output_whole = post_process_ttl_file(g, valid_properties)
    print(f'Visualizing the result')
    generate_visual_graph(g)

    return ttl_output_whole


def generate_visual_graph(g):
    nodes = []
    for (s, p, o) in g:
        nodes.append(s)
        nodes.append(o)
        # VG.add_edge(s, p, o)
    node_data = list(set(nodes))
    node_label_to_id = {}
    graph_nodes = []
    graph_edges = []
    for i in range(0, len(node_data)):
        shortened_iri = node_data[i].replace("https://schema.org/", "schema:")
        shortened_iri = shortened_iri.replace("https://my.example.com/", "ex:")
        graph_nodes.append(Node(id=i, size=10, label=shortened_iri, title=shortened_iri))
        node_label_to_id[node_data[i]] = i
    for (s, p, o) in g:
        shortened_iri = p.replace("https://schema.org/", "schema:")
        shortened_iri = shortened_iri.replace("https://my.example.com/", "ex:")
        shortened_iri = shortened_iri.replace("http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "a")

        graph_edges.append(Edge(source=node_label_to_id[s], label=shortened_iri, target=node_label_to_id[o]))
    config = Config(width=600,
                    height=750,
                    directed=True,
                    physics=True,
                    hierarchical=False,
                    highlightColor="#F7A7A6",
                    edgeMinimization=False
                    # **kwargs
                    )
    agraph(nodes=graph_nodes,
           edges=graph_edges,
           config=config)


def generate_response(input_text):
    # llm = OpenAI(temperature=0.7, openai_api_key=openai_api_key)
    ttl_file = convert_text_to_kg(input_text)
    st.code(ttl_file)
    return ttl_file


def clear_text():
    st.session_state["text"] = ""


with st.form('text_form'):
    text = st.text_area('Enter text:', key="text")
    submitted = st.form_submit_button('Submit')
    clear_btn = st.form_submit_button('Clear', on_click=clear_text)
    if not openai_api_key.startswith('sk-'):
        st.warning('Please enter your OpenAI API key!', icon='⚠')
    if submitted and openai_api_key.startswith('sk-'):
        st.session_state.submitted = True
        if 'submitted' in st.session_state:
            data_to_download = generate_response(text)

if 'submitted' in st.session_state and data_to_download is not None:
    st.download_button(label='Download', data=data_to_download, file_name='kg.ttl')
