from openai import OpenAI
from rdflib import Graph
import re
import nltk
from nltk.tokenize import sent_tokenize

nltk.download('punkt')


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


def get_ontology(temp, prompt_messages, openai_api_key):
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


def split_text_into_chunks(txt, max_chunk_size=2000, min_chunk_size=100):
    if not isinstance(txt, str):
        raise TypeError("Input text must be a string")

    paragraphs = []
    sentences = sent_tokenize(txt)

    curr_paragraph_size = 0
    curr_paragraph = ""
    for s in sentences:
        sent = s.strip()
        print(f"Sentence length is {len(sent)}")
        if curr_paragraph_size != 0 and curr_paragraph_size + len(sent) < min_chunk_size:
            curr_paragraph += sent + " "
            curr_paragraph_size += len(sent) + 1
        elif curr_paragraph_size != 0 and curr_paragraph_size + len(sent) > max_chunk_size:
            curr_paragraph += "\n"
            paragraphs.append(curr_paragraph)
            curr_paragraph = sent + " "
            curr_paragraph_size = len(sent) + 1
        else:
            curr_paragraph += sent + " "
            curr_paragraph_size += len(sent) + 1
    if curr_paragraph != "":
        paragraphs.append(curr_paragraph)
    return paragraphs

