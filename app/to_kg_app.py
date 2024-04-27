import streamlit as st
from rdflib import Graph
from rdflib.plugins.parsers.notation3 import BadSyntax
from streamlit_agraph import agraph, Node, Edge, Config

import helpers.helper as helper

st.set_page_config(layout="wide")

st.title('Convert Text to Knowledge Graph')

openai_api_key = st.sidebar.text_input('OpenAI API Key', type='password')
modelGpt = "gpt-4-turbo-preview"

log_message = st.empty()


def convert_text_to_kg(text):
    chunk_size = 1500
    chunks = helper.split_text_into_chunks(text, max_chunk_size=chunk_size)
    args = {
        'temperature': 0.35,
        'max_new_tokens': 2048,
        # 'protocols_dir': '/content/drive/MyDrive/Thesis/week0/protocols/MI/protocol',
        # 'output_dir': '/content/drive/MyDrive/Thesis/week1/results/gpt-4-turbo/MI'
    }

    g = Graph()
    g, ttl_output_whole = generate_knowledge_graph(args, chunks, g)
    g.parse(data=ttl_output_whole, format='ttl')

    print(f'Visualizing the result')
    generate_visual_graph(g)
    log_message.empty()

    return ttl_output_whole


def generate_knowledge_graph(args, chunks, g):
    ttl_output_whole = ""
    chunks_size = len(chunks)
    for (i, chunk) in enumerate(chunks, start=1):
        print(f"Parsing chunk {chunk}")
        messages = helper.format_initial_messages(helper.get_system_prompt(), chunk)
        print(f'Step {1 * i}/{5 * chunks_size} Prompting the LLM for initial knowledge graph...')
        log_message.info(f"Step {1 * i}/{5 * chunks_size} Prompting the LLM for initial knowledge graph...")
        model_ontology_output = helper.get_ontology(args['temperature'], messages, openai_api_key)
        print("Finished first step of the pipeline")
        log_message.info("Finished first step of the pipeline")
        messages.append(helper.format_single_part_conversation('assistant', model_ontology_output))
        messages.append(
            helper.format_single_part_conversation('user', helper.get_missed_statements_prompt(chunk, model_ontology_output)))
        print(f"Step {2 * i}/{5 * chunks_size} Prompt for revision of the current knowledge graph...")
        log_message.info(f"Step {2 * i}/{5 * chunks_size} Prompt for revision of the current knowledge graph...")
        revised_comments = helper.get_ontology(args['temperature'], messages, openai_api_key)
        print("Finished second step of the pipeline")
        log_message.info("Finished second step of the pipeline")
        messages.append(helper.format_single_part_conversation('assistant', revised_comments))
        messages.append(helper.format_single_part_conversation('user', helper.get_final_ontology_prompt()))
        print(f"Step {3 * i}/{5 * chunks_size} Prompting for finalized knowledge graph...")
        log_message.info(f"Step {3 * i}/{5 * chunks_size} Prompting for finalized knowledge graph...")
        final_ontology = helper.get_ontology(args['temperature'], messages, openai_api_key)
        print(f"Step {4 * i}/{5 * chunks_size} Extracting file in turtle format...")
        log_message.info(f"Step {4 * i}/{5 * chunks_size} Extracting file in turtle format...")
        # print(f"Final ontology is {final_ontology}")
        ttl_output = helper.extract_ttl_content_gpt(final_ontology)
        print(f"Step {5 * i}/{5 * chunks_size} Merging chunks...")
        log_message.info(f"Step {5 * i}/{5 * chunks_size} Merging chunks...")

        if len(ttl_output) != 0:
            # merging
            try:
                g1 = Graph()
                g1.parse(data=ttl_output, format='ttl')
                g += g1
                ttl_output_whole += ttl_output
            except BadSyntax:
                st.error('An error occurred during the parsing of the generated file', icon="🚨")
                print(f"Error in Turtle syntax")
                log_message.empty()
    return g, ttl_output_whole


def generate_visual_graph(g):
    nodes = []
    for (s, p, o) in g:
        nodes.append(s)
        nodes.append(o)
    node_data = list(set(nodes))
    node_label_to_id = {}
    graph_nodes = []
    graph_edges = []
    blank_node_index = 0
    for i in range(0, len(node_data)):
        shortened_iri = node_data[i].replace("http://hl7.org/fhir/", "fhir:")
        shortened_iri = shortened_iri.replace("http://hl7.org/fhir/action:", "fhira:")
        shortened_iri = shortened_iri.replace("http://hl7.org/fhir/expression:", "fhirexp:")
        shortened_iri = shortened_iri.replace("http://hl7.org/fhir/condition:", "fhircond:")
        shortened_iri = shortened_iri.replace("http://example.com/", "ex:")
        if shortened_iri.startswith("n"):  # Check if the string starts with 'nc'
            shortened_iri = f"n_{blank_node_index}"  # Replace with 'nc_i'
            blank_node_index += 1
        graph_nodes.append(Node(id=i, size=10, label=shortened_iri, title=shortened_iri))
        node_label_to_id[node_data[i]] = i
    for (s, p, o) in g:
        shortened_iri = p.replace("http://hl7.org/fhir/", "fhir:")
        shortened_iri = shortened_iri.replace("http://hl7.org/fhir/action:", "fhira:")
        shortened_iri = shortened_iri.replace("http://hl7.org/fhir/expression:", "fhirexp:")
        shortened_iri = shortened_iri.replace("http://hl7.org/fhir/condition:", "fhircond:")
        shortened_iri = shortened_iri.replace("http://example.com/", "ex:")
        shortened_iri = shortened_iri.replace("http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "a")

        graph_edges.append(Edge(source=node_label_to_id[s], label=shortened_iri, target=node_label_to_id[o]))

    config = Config(width=1600,
                    height=1000,
                    directed=True,
                    physics=False,
                    hierarchical=False,
                    highlightColor="#F7A7A6",
                    edgeMinimization=False
                    # **kwargs
                    )
    agraph(nodes=graph_nodes,
           edges=graph_edges,
           config=config)


def generate_response(input_text):
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
