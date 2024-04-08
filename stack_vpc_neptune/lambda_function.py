import json
import traceback
from langchain_community.graphs import NeptuneGraph
from langchain.chains import NeptuneOpenCypherQAChain
from langchain.llms.bedrock import Bedrock
from gremlin_python.structure.graph import Graph
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.graph_traversal import __
from gremlin_python import statics
from gremlin_python.driver import client


def ask_graph(llm_query, neptune_endpoint, region_name="us-west-2"):
    """
    @llm_query (type str):
        Natural language query to submit to Bedrock's model (e.g. Anthropic Claude), via LangChain
        e.g. "how many scooters do I have?"

    @neptune_endpoint (type str):
        writer or reader Neptune endpoint are supported for this function. Port (optionally) hard-coded.
    """
    # Get model inference parameters. Feel free to change the model and inference params.
    model = 'anthropic.claude-v2:1'
    model_kwargs = {
        "max_tokens_to_sample": 512,
        "temperature": 0, 
        "top_k": 250, 
        "top_p": 1, 
        "stop_sequences": ["\n\nHuman:"] 
        }

    try:
        # Model setup, using LangChain. 
        # - More at: https://python.langchain.com/docs/use_cases/graph/neptune_cypher_qa
        graph = NeptuneGraph(host=neptune_endpoint, port=8182, use_https=True)
        llm = Bedrock(
            region_name=region_name,
            model_id=model,
            model_kwargs = model_kwargs
        )

        # Create Prompt template. Remember this can change for every model. 
        prompt_template = f"""
            Human: Do not apologize and just respond the question directly.  
            
            question: {llm_query}

            Assistant:"""

        # Let's use NL to ask our LLM to traverse the graph
        chain = NeptuneOpenCypherQAChain.from_llm(llm=llm, graph=graph, verbose=True)
        llm_response = chain.run(prompt_template)

        return llm_response

    except Exception as e:
        print('Error while calling Amazon Bedrock and LangChain: {}'.format(e))
        traceback.print_exc()


def query_scooter_asset(scooter_asset_code, neptune_endpoint):
    """
    @scooter_asset_code (type str):
        asset code; e.g. scooter-9999, part-9999, incident-9999, driver-9999

    @neptune_endpoint (type str):
        writer or reader Neptune endpoint are supported for this function. Port (optionally) hard-coded.
    """
    # Neptune settings:
    graph = Graph()
    statics.load_statics(globals())

    try:
        # Neptune connection, forcing port here:
        remoteConn = DriverRemoteConnection('wss://{}:8182/gremlin'.format(neptune_endpoint),'g')
        g = graph.traversal().withRemote(remoteConn)

        # Run query:
        query_response = g.V(scooter_asset_code).repeat(__.out()).until(not_(__.out('has'))).valueMap(True).toList()

        # Temporary workaround, to format response from Neptune. i.e. valueMap() returns non-dict keys; to investigate
        # - To try: json.dumps(query_response, separators=(',', ':'), indent=4)
        query_response = str(query_response).replace("<T", "'T").replace(">:", "':")
        query_response = json.dumps(query_response, indent=4)

        # Close connection; see instead
        remoteConn.close()

        # Return to be enriched. Pending to remove multiple JSON casts.
        return json.loads(query_response)

    except Exception as e:
        print('Error while querying Neptune: {}'.format(e))
        traceback.print_exc()


def run_gremlin_query(gremlin_query, neptune_endpoint):
    """
    Temporary feature for testing: open query. 
    - IMPORTANT: treat this (ApiGateway-IP-protected) function carefully, as it opens direct comms to the DB
    
    @gremlin_query (type str):
        Gremlin query; e.g. g.V().hasLabel('scooter').out().limit(5).toList()

    @neptune_endpoint (type str):
        writer or reader Neptune endpoint are supported for this function. Port (optionally) hard-coded
    """
    # Neptune settings:
    graph = Graph()
    statics.load_statics(globals())

    try:
        # Temporary feature for testing
        gremlin_client = client.Client('wss://{}:8182/gremlin'.format(neptune_endpoint),'g')

        # Run query:
        query_submit = gremlin_client.submit(gremlin_query)
        query_results = query_submit.all()
        query_results = query_results.result()

        # Temporary workaround, to format response from Neptune. Fn valueMap() returns non-dict keys.
        # - To keep testing; i.e. json.dumps(query_response, separators=(',', ':'), indent=4)
        query_response = str(query_results).replace("<T", "'T").replace(">:", "':")
        query_response = json.dumps(query_response, indent=4)

        # Close connection; see instead
        gremlin_client.close()

        # Return to be enriched. Pending to remove multiple JSON casts.
        return json.loads(query_response)

    except Exception as e:
        print('Error while querying Neptune: {}'.format(e))
        traceback.print_exc()


def lambda_handler(event, context):
    # Input parameter for all functions:
    neptune_endpoint = event['queryStringParameters']['neptune_endpoint']

    # Eval Rest call:
    if event['path'] == '/getScooter':
        # Read input parameters
        scooter_asset_code = event['queryStringParameters']['scooter_asset_code']
    
        # Run query against Neptune database
        response = query_scooter_asset(scooter_asset_code=scooter_asset_code, neptune_endpoint=neptune_endpoint)
        response_status = 201
    
    elif event['path'] == '/runQuery':
        # Read input parameters
        gremlin_query = event['queryStringParameters']['gremlin_query']

        # Run query against Neptune database
        response = run_gremlin_query(gremlin_query=gremlin_query, neptune_endpoint=neptune_endpoint)
        response_status = 202

    elif event['path'] == '/askGraph':
        # Read input parameters
        nl_question = event['queryStringParameters']['llm_query']

        # Run query against Neptune database. Confirm default region.
        response = ask_graph(llm_query=nl_question, neptune_endpoint=neptune_endpoint)
        response_status = 203
    
    else:
        # Better response call to be added
        response = json.dumps('Error: method name does not exist. Confirm names at the docs!')
        response_status = 400
    
    # Return headers to allow CORS access, for localhost testing; source: https://go.aws/3UiTS5X
    return {
            'statusCode': response_status,
            'headers': {
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
            },
            'body': response
        }
