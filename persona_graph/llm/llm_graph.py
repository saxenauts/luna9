import json
import openai
from typing import List, Tuple, Dict
from persona_graph.llm.prompts import GET_NODES, GET_RELATIONSHIPS, GENERATE_COMMUNITIES
from persona_graph.models.schema import EntityExtractionResponse, NodesAndRelationshipsResponse, CommunityStructure
from app_server.config import config
import instructor
from instructor import OpenAISchema
from pydantic import Field
from persona_graph.utils.instructions_reader import INSTRUCTIONS

# Initialize the OpenAI client globally if not already set up elsewhere in your application
openai_client = openai.AsyncOpenAI(api_key=config.MACHINE_LEARNING.OPENAI_KEY)
client = instructor.from_openai(openai_client)

class Node(OpenAISchema):
    name: str
    perspective: str

class Relationship(OpenAISchema):
    source: str
    relation: str
    target: str

class GraphResponse(OpenAISchema):
    nodes: List[Node] = Field(..., description="List of nodes in the graph")
    relationships: List[Relationship] = Field(default_factory=list, description="List of relationships between nodes")

async def get_nodes(text: str, schema_context: str) -> List[Node]:
    """
    Extract nodes from provided text using OpenAI's language model.
    """
    try:
        combined_instructions = f"App Objective: {INSTRUCTIONS}\n\nExisting Schema and User Graph Context: {schema_context}\n\nNode Extraction Task: {GET_NODES}"
        response = await client.chat.completions.create(
            model='gpt-4o-mini', #TODO: Make this a variable controlled by the config. 
            messages=[
                {"role": "system", "content": combined_instructions},
                {"role": "user", "content": text}
            ],
            temperature=0.5,
            response_model=List[Node]
        )
        # Extract entities from response, assuming the expected format is JSON
        return response
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return []
    except Exception as e:
        print(f"Error while extracting nodes: {e}")
        return []

async def get_relationships(nodes: List[Node], graph_context: str, schema_context: str) -> List[Relationship]:
    """
    Generate relationships based on the list of nodes and existing graph context using OpenAI's language model.
    """
    #TODO: Add user psyche context, and new node specific context to the prompt. 
    nodes_str = ', '.join([node.name + ' (' + node.perspective + ')' for node in nodes])
    combined_instructions = f"App Objective: {INSTRUCTIONS}\n\nRelationships Generation Task: {GET_RELATIONSHIPS}"
    try:
        response = await client.chat.completions.create(
            model='gpt-4o-mini', #TODO: Make this a variable controlled by the config. 
            messages=[
                {"role": "system", "content": combined_instructions},
                {"role": "user", "content": f"Existing Schema:\n{schema_context}\n\nNodes: {nodes_str}\n\nExisting Graph Context:\n{graph_context}"}
                
            ],
            temperature=0.7,
            response_model=List[Relationship]
        )
        relationships = response
        return relationships
    except Exception as e:
        print(f"Error while generating relationships: {e}")
        return []

async def generate_response_with_context(query: str, context: str) -> str:
    prompt = f"""
    Given the following context from a knowledge graph and a query, provide a detailed answer:

    Context:
    {context}

    Query: {query}

    Please provide a comprehensive answer based on the given context:
    """

    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": prompt},
            {"role": "system", "content": "You are a helpful assistant that answers queries about a user based on the provided context from their graph."},
            
        ]
    )
    return response.choices[0].message.content

# You can further use these functions in your application to update the graph or for other processes.

async def detect_communities(subgraphs_text: str) -> CommunityStructure:
    """
    Use LLM to detect communities in the graph and organize them into headers/subheaders
    """
    try:
        response = await client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {"role": "system", "content": GENERATE_COMMUNITIES},
                {"role": "user", "content": subgraphs_text}
            ],
            temperature=0.7,
            response_model=CommunityStructure
        )
        print("Community Detection Response: ", response)
        return response
    except Exception as e:
        print(f"Error in community detection: {str(e)}")
        return CommunityStructure(communityHeaders=[])