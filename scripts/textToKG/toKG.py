import click
from openai import OpenAI
from rdflib import Graph
import re
import sys
import os
import csv


def read_file(filenames):
    if filenames and filenames[0] == '-':
        return sys.stdin.read()
    else:
        for filename in filenames:
            with open(filename, 'r') as f:
                protocol = f.read()
                return protocol


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


def get_ontology(temp, prompt_messages, api_key):
    client = OpenAI(api_key=api_key)
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
    return result_ontology


@click.command()
@click.argument('filenames', nargs=-1)
@click.argument('output', nargs=1)
@click.argument('api_key', nargs=1)
@click.argument('retry', nargs=1)
def convert_text_to_kg(filenames, output, api_key, retry):

    chunk_size = 1500
    chunks = []
    print(f'Reading the file...')
    if not filenames and not sys.stdin.isatty():
        lines = sys.stdin
    else:
        lines = read_file(filenames)

    curr_chunk_size = 0
    curr_chunk = ""
    for line in lines.splitlines():
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
        g1 = Graph()
        ttl_output = infer_ontology(api_key, args, chunk)
        while True:
            if len(ttl_output) != 0:
                # merging
                try:
                    g1.parse(data=ttl_output, format='ttl')
                    ttl_output_whole += ttl_output
                    g += g1
                    break
                except Exception as e:
                    print(f"Error paring in TTL: ", e)
                    if bool(retry):
                        ttl_output = infer_ontology(api_key, args, chunk)
                    else:
                        break

    print(f'Writing the file...')
    g.serialize(destination=output, format='turtle')
    print(f'Written {output}')


def infer_ontology(api_key, args, chunk):
    messages = format_initial_messages(get_system_prompt(), chunk)
    model_ontology_output = get_ontology(args['temperature'],
                                         messages, api_key)
    print("Finished first step of the pipeline")
    messages.append(format_single_part_conversation('assistant', model_ontology_output))
    messages.append(format_single_part_conversation('user',
                                                    get_missed_statements_prompt(chunk, model_ontology_output)))
    revised_comments = get_ontology(args['temperature'], messages, api_key)
    print("Finished second step of the pipeline")
    messages.append(format_single_part_conversation('assistant', revised_comments))
    messages.append(format_single_part_conversation('user', get_final_ontology_prompt()))
    final_ontology = get_ontology(args['temperature'], messages, api_key)
    print("Extracting file in turtle format...")
    ttl_output = extract_ttl_content_gpt(final_ontology)
    print("Merging chunks...")
    return ttl_output


if __name__ == "__main__":
    convert_text_to_kg()
