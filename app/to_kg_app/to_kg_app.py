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
modelGpt = "gpt-4-turbo-preview"

log_message = st.empty()


def extract_ttl_content_gpt(text):
    ttl_pattern = r'```ttl\n([\s\S]*?)\n```'
    matches = re.search(ttl_pattern, text)
    return matches.group(1) if matches else text


def get_system_prompt():
    return f"""Use the context of medicine. Translate the following user text to an RDF graph using the HL7 FHIR standard formatted as TTL. Use appropriate and valid classes and properties listed on HL7 FHIR to represent entities and their attributes."""


def get_missed_statements_prompt(protocol, kg_candidate):
    return f"""Given the initial knowledge graph in Turtle (TTL) format, created from a medical text using HL7 FHIR standard and the prefix ex: with IRI <http://example.com/> for any created entities or properties, perform a detailed revision of the graph. Evaluate the graph based on the following criteria:


Completeness: Assess whether the knowledge graph includes all relevant information provided in the text. Identify any missing entities, attributes, or relationships that are mentioned in the text but not represented in the graph.


Specificity: Examine the use of HL7 FHIR vocabulary in the graph. Determine if the classes and properties used accurately and specifically represent the information from the text. Highlight any instances where more specific HL7 FHIR terms could better represent the details provided.


Fidelity to Text: Evaluate the knowledge graph's adherence to the text. Identify any assumptions, extrapolations, or additions not directly supported by the text. Ensure that every element of the knowledge graph can be traced back to explicit information provided in the text.


Text: {protocol}
initial knowledge graph in Turtle (TTL) format: {kg_candidate}


Objective:


Generate precise comments on each of the above components, highlighting areas for improvement. Your feedback should include:


Specific entities, attributes, or relationships that are missing (for Completeness).
Suggestions for more accurate or specific HL7 FHIR classes and properties (for Specificity).
Points of deviation from the text, including any assumptions or unwarranted additions (for Fidelity to Text).
This detailed evaluation and feedback will inform the creation of a revised knowledge graph that aims to fully capture the text's information with high fidelity, leveraging the appropriate and specific HL7 FHIR vocabulary.
"""


def get_final_ontology_prompt():
    return f"""Based on the identified gaps and inaccuracies, generate a revised knowledge graph in TTL format using HL7 FHIR standard, ensuring it more accurately reflects the text's content."""


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


def get_ontology(temp, prompt_messages):
    client = OpenAI(api_key=openai_api_key)
    chat_completion = client.chat.completions.create(
        messages=prompt_messages,
        model="gpt-4-turbo-preview",
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
    # print(f"result ontology: {result_ontology}")
    # print(f"serialized result ontology: {g.serialize(format='ttl')}")
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
    log_message.info("Prompting the LLM...")
    client = OpenAI(api_key=openai_api_key)
    g = Graph()
    ttl_output_whole = ""
    for chunk in chunks:
        messages = format_initial_messages(get_system_prompt(), chunk)
        model_ontology_output = get_ontology(args['temperature'],
                                             messages)
        print("Finished first step of the pipeline")
        log_message.info("Finished first step of the pipeline")
        messages.append(format_single_part_conversation('assistant', model_ontology_output))
        messages.append(format_single_part_conversation('user', get_missed_statements_prompt(chunk, model_ontology_output)))
        revised_comments = get_ontology(args['temperature'], messages)
        print("Finished second step of the pipeline")
        log_message.info("Finished second step of the pipeline")
        messages.append(format_single_part_conversation('assistant', revised_comments))
        messages.append(format_single_part_conversation('user', get_final_ontology_prompt()))
        final_ontology = get_ontology(args['temperature'], messages)
        print("Extracting file in turtle format...")
        log_message.info("Extracting file in turtle format...")
        print(f"Final ontology is {final_ontology}")
        ttl_output = extract_ttl_content_gpt(final_ontology)
        print("Merging chunks...")
        log_message.info("Merging chunks...")
        if len(ttl_output) != 0:
            ttl_output_whole += ttl_output
        # merging
            try:
                g1 = Graph()
                g1.parse(data=ttl_output, format='ttl')
                g += g1
            except BadSyntax:
                st.error('An error occurred during the parsing of the generated file', icon="🚨")
                print(f"Error in Turtle syntax")
                log_message.empty()

    # valid_properties = load_valid_properties()
    # print("Post-processing the result ontology...")
    # log_message.info("Post-processing the result ontology...")
    # ttl_output_whole = post_process_ttl_file(g, valid_properties)
    print(f'Visualizing the result')
    generate_visual_graph(g)
    log_message.empty()

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
        shortened_iri = node_data[i].replace("http://hl7.org/fhir/", "fhir:")
        shortened_iri = shortened_iri.replace("http://example.com/", "ex:")
        graph_nodes.append(Node(id=i, size=10, label=shortened_iri, title=shortened_iri))
        node_label_to_id[node_data[i]] = i
    for (s, p, o) in g:
        shortened_iri = p.replace("http://hl7.org/fhir/", "fhir:")
        shortened_iri = shortened_iri.replace("http://example.com/", "ex:")
        shortened_iri = shortened_iri.replace("http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "a")

        graph_edges.append(Edge(source=node_label_to_id[s], label=shortened_iri, target=node_label_to_id[o]))
    config = Config(width=800,
                    height=1000,
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

my_message = st.empty()

if 'submitted' in st.session_state and data_to_download is not None:
    st.download_button(label='Download', data=data_to_download, file_name='kg.ttl')
