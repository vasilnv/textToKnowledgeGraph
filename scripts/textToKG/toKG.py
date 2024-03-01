import click
from openai import OpenAI
from rdflib import Graph
import re
from rdflib.plugins.parsers.notation3 import BadSyntax
import sys

def read_file(filenames):
    if filenames and filenames[0] == '-':
        return sys.stdin.read()
    else:
        for filename in filenames:
            with open(filename, 'r') as f:
                protocol = f.read()
                return protocol

def extract_ttl_content(text):
    ttl_pattern = r'```ttl\n([\s\S]*?)\n```'
    matches = re.search(ttl_pattern, text)
    return matches.group(1) if matches else None

def get_system_prompt():
    return f"""Use the context of medicine. Translate the following user text to an RDF graph using the SCHEMA.ORG ontology formatted as TTL. Use only valid entities (such as schema:MedicalCondition, schema:MedicalSignOrSymptom, schema:MedicalTest, schema:Drug) and properties (such as schema:possibleTreatment, schema:causeOf, schema:signOrSymptom, schema:usedToDiagnose, schema:drug, schema:possibleComplication, schema:guideline) listed on SCHEMA.ORG.
Not allowed relations: schema:indication, schema:indicates, schema:indications, schema:indicate, schema:partOf , schema:prevalence, schema:cause , schema:outcome, schema:subProcedure, schema:isA, schema:complication.
    
Use the prefix ex: with IRI <http://example.com/> for any created entities or properties."""

def get_ontology_1(system_prompt, protocol, temp):
    client = OpenAI(api_key="<YOUR-API-KEY>")
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

@click.command()
@click.argument('filenames', nargs=-1)
@click.argument('output', nargs=1)
def convert_text_to_kg(filenames, output):

    chunk_size = 100
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
        'temperature': 0.3,
        'max_new_tokens': 2048
    }


    print(f'Prompting the LLM...')
    g = Graph()
    for (chunk_id, chunk) in enumerate(chunks):
        model_ontology_output = get_ontology_1(get_system_prompt(), chunk, args['temperature'])
        ttl_output = extract_ttl_content(model_ontology_output)
        print(f'TTL OUTPUT IS {ttl_output}')
        # merging
        try:
            g1 = Graph()
            g1.parse(data=ttl_output, format='ttl')
            g += g1
        except BadSyntax:
            print(f"Error in Turtle syntax: {chunk_id}")


    print(f'Writing the file...')
    # with open(output, 'w', encoding='utf8') as out_file:
    #     out_file.write(ttl_output)
    g.serialize(destination=output, format='turtle')
    print(f'Written {output}')

if __name__ == "__main__":
    convert_text_to_kg()