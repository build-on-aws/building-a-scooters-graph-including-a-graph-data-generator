import awswrangler as wr
import os
import pandas as pd
import random
import string
import traceback
import json
import uuid
from anytree import Node, RenderTree

"""
Important:  This Lambda function is not intended for production environments, nor for high volumes; 
            i.e. Millions of data points. It's just for demo-purposes.

    Volume and performance estimate (this fn can be executed in parallel, if required)
    - For 100 scooters and 5 parts each, duration = ~0.5s. These params are defined in our CDK/app.py project
    - For 10,000 scooters and 10 parts each, duration = ~18s. This generates ~360,000 connected nodes, incl. scooters, parts, manufacturers, faults, etc. 
"""

def randomize_scooter_asset(asset, num_chars=6):
    """
    To make this dummy dataset more realistic, we randomize all scooter asset names
    :param asset: scooter component to randomize, by adding a suffix.

    :return: randomized asset
    """

    # Generate random suffix
    random_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=num_chars))

    if asset == 'part':
        # Define some scooter parts
        parts = ['front_tyre','back_tyre','axle','transmission','suspension','battery','steering','catalytic_converter','ignition_pipe','brake']
        random_asset = '{}_{}-{}'.format(asset, random.choice(parts), random_string)

    else:
        random_asset = '{}-{}'.format(asset, random_string)

    return random_asset


def randomize_chances(odds_one_to_many=4):
    """
    To make this dummy dataset more realistic, we randomize faults, scooter-at-warehouse vs scooter-already-sold, etc.
    - We first create a list with a single element, number 1, and then we add N zeroes (odds_one_to_many) to the list.
    - Finally, the random.choice function will pick one of these elements of the list (a single 1 and multiple 0). 

    :odds_one_to_many, type int: is the odds ratio (OR) for N
    :return: 1 or 0, picking one of these two randomly from array of <<odds_one_to_many>>
    """
    odds_picker = [1]

    for x in range(odds_one_to_many):
        odds_picker.append(0)
    
    return random.choice(odds_picker)


def generate_scooter_vertices(number_of_scooters, number_of_parts_per_scooter, s3_bucket_name, s3_prefix, write_to_s3, show_tree_on_screen):
    """
    Generates, and optionally writes, scooters Vertices dataset in Gremlin for Neptune format.
        @Note: This code is not optimized for large volumes of data, e.g. millions. 
    :param number_of_scooters: how many scooters we want to generate for this dummy data
    :param number_of_parts_per_scooter: how many parts per scooter
    :param write_to_s3: boolean flag to write to s3

    :return: Pandas dataframe with Vertices in Gremlin Neptune format
    """
    # Placeholder array to save all generated data
    all_scooters = []

    try:
        # Create X number of scooters and randomize names
        for x in range(1, int(number_of_scooters)+1):
            scooter = Node(randomize_scooter_asset('scooter'))

            # Begin: Scooters Incidents
            if randomize_chances(odds_one_to_many=10) == 1:
                incident = Node(randomize_scooter_asset('incident'), parent=scooter)
                legal_case = Node(randomize_scooter_asset('legal_case'), parent=incident)

            # Begin: Scooters Parts, manufacturers and legal warranties
            for i in range(1, int(number_of_parts_per_scooter)+1):
                part = Node(randomize_scooter_asset('part'), parent=scooter)
                part_manufacturer = Node(randomize_scooter_asset('manufacturer',2), parent=part)
                part_legal_warranty = Node(randomize_scooter_asset('legal_warranty'), parent=part)

            # Begin: Scooter's Location
            if randomize_chances(odds_one_to_many=3) == 0:
                scooter_in_transit = Node(randomize_scooter_asset('in_transit_journey'), parent=scooter)
                
                # Begin: Weather
                if randomize_chances(odds_one_to_many=3) == 1:
                    weather = Node('weather_sunny-ws1', parent=scooter_in_transit)
                elif randomize_chances(odds_one_to_many=2) == 1:
                    weather = Node('weather_cloudy-wc3', parent=scooter_in_transit)
                else:
                    weather = Node('weather_rainy-wr2', parent=scooter_in_transit)

            # Begin: less-likely locations
            elif randomize_chances(odds_one_to_many=10) == 1:
                loc_warehouse = Node(randomize_scooter_asset('warehouse',1), parent=scooter)
            elif randomize_chances(odds_one_to_many=2) == 1:
                loc_parking_station = Node(randomize_scooter_asset('parking_station',2), parent=scooter)
            elif randomize_chances(odds_one_to_many=10) == 1:
                loc_maintenance_center = Node(randomize_scooter_asset('maintenance_center',2), parent=scooter)
            else:
                # If none was selected by N random functions, we place it back on the streets: 
                scooter_in_transit = Node(randomize_scooter_asset('in_transit_journey'), parent=scooter)

            # Begin: Driver's payments
            driver = Node(randomize_scooter_asset('driver'), parent=scooter)
            if randomize_chances(odds_one_to_many=4) == 1:
                payment_method = Node('payment_method-credit-card-visa', parent=driver)
            elif randomize_chances(odds_one_to_many=3) == 1:
                payment_method = Node('payment_method-credit-card-mastercard', parent=driver)
            elif randomize_chances(odds_one_to_many=3) == 1:
                payment_method = Node('payment_method-google-pay', parent=driver)
            else:
                payment_method = Node('payment_method-apple-pay', parent=driver)

            # Begin: Faulty parts
            if randomize_chances(odds_one_to_many=4) == 1:
                part_fault = Node(randomize_scooter_asset('fault',2), parent=part)
                fault_warranty = Node(randomize_scooter_asset('warranty'), parent=part_fault)
                
                # From those with a fault, only some will have a claim
                if randomize_chances(odds_one_to_many=4) == 1:
                    claim_fault = Node(randomize_scooter_asset('claim_fault'), parent=part_fault)

            # Begin: Fleet Owners
            if randomize_chances(odds_one_to_many=4) == 1:
                fleet_owner = Node('fleet_owner-pegasus-scooters', parent=scooter)
            elif randomize_chances(odds_one_to_many=3) == 1:
                fleet_owner = Node('fleet_owner-pineapple-scooters', parent=scooter)
            else:
                fleet_owner = Node('fleet_owner-evfast-scooters', parent=scooter)

            # Begin: Building dataset
            if show_tree_on_screen:
                # @ Example to show all assets, in a hierarchy tree format>
                for pre, fill, node in RenderTree(scooter):
                    print("%s %s" % (pre, node.name))

            for pre, fill, node in RenderTree(scooter):
                # AnyTree doesn't seem to have a better way to return specific elements from Node.Parent;
                #   i.e. immediate parent and not all hierarchy
                parent_node = str(node.parent).split('/', -1)[-1]
                parent_node = parent_node.replace("'", "").replace(")", "")
                node_asset_label = node.name.split('-', 1)[0]
                
                # Dict init, which will hold all scooter data
                scooter_dict = {'~label': node_asset_label, '~id': node.name, 'parent_id': parent_node, 'name': node.name}
                all_scooters.append(scooter_dict)
            
        # Populate DF
        df_scooters = pd.DataFrame.from_records(all_scooters)

        if write_to_s3:
            # Storing data to s3; for local tests use boto3_session=boto3_session
            wr.s3.to_csv(
                df=df_scooters,
                path='s3://{}/{}/vertices.csv'.format(s3_bucket_name, s3_prefix),
                dataset=False,
                index=False
            )

        return df_scooters

    except Exception as e:
        print('Error while generating vertices: {}'.format(e))
        traceback.print_exc()


def generate_scooter_edges(input_df, s3_bucket_name, s3_prefix, write_to_s3):
    """
    Generates, and optionally writes, scooters Edges dataset in Gremlin for Neptune format
    :param input_df: pandas dataframe with scooters vertices dataset
    :param write_to_s3: boolean flag to write to s3

    :return: str
    """
    try:
        # add Edge label. This can be changed to CASE-WHEN, to change it for every case:  
        # - e.g. has_claim, has_fault, has_manufactures, etc.
        input_df['~label'] = 'has'

        # remove root vertices (no parent)
        df_scooters = input_df[input_df.parent_id != 'None']

        # rename columns only, to generate pseudo-columns for Gremlin loader
        # - to invert graph direction, swap id and parent; e.g. {'~id': '~from', 'parent_id': '~to'}
        df_scooters = df_scooters.rename({'~id': '~to', 'parent_id': '~from'}, axis=1)

        # add random id, for the Neptune loader
        df_scooters['~id'] = [uuid.uuid4() for _ in range(len(df_scooters.index))]

        if write_to_s3:
            # Amazon S3 output path:
            s3_edges_output = 's3://{}/{}/edges.csv'.format(s3_bucket_name,s3_prefix)

            # Storing data to s3; for local tests use boto3_session=boto3_session
            wr.s3.to_csv(
                df=df_scooters,
                path=s3_edges_output,
                dataset=False,
                index=False
            )

        return {
            'statusCode': 200,
            'body': json.dumps(f"Successful execution. Edges written to {s3_edges_output}")
            }

    except Exception as e:
        print('Error while generating edges: {}'.format(e))
        traceback.print_exc()


# Run main
def lambda_handler(event, context):
    # OS Input parameters:
    input_s3_bucket_name = os.environ['s3_bucket_name']
    input_s3_prefix = os.environ['s3_prefix']
    input_num_of_vehicles = os.environ['datagen_num_of_vehicles']
    input_num_of_parts_per_vehicle = os.environ['datagen_num_of_parts_per_vehicle']

    # Hard-coded values, so user can test locally:
    input_print_tree_on_screen = False
    input_write_to_s3_flag = True

    # Generate data:
    response_vertices = generate_scooter_vertices(number_of_scooters=input_num_of_vehicles, 
                                                    number_of_parts_per_scooter=input_num_of_parts_per_vehicle, 
                                                    show_tree_on_screen=input_print_tree_on_screen, 
                                                    write_to_s3=input_write_to_s3_flag,
                                                    s3_bucket_name=input_s3_bucket_name,
                                                    s3_prefix=input_s3_prefix)

    response_edges = generate_scooter_edges(input_df=response_vertices, 
                                                    write_to_s3=input_write_to_s3_flag,
                                                    s3_bucket_name=input_s3_bucket_name,
                                                    s3_prefix=input_s3_prefix)
    
    return {
            'statusCode': 200,
            'body': json.dumps(f"""
                               OK: Graph data generated at s3://{input_s3_bucket_name}/{input_s3_prefix}, 
                               for {input_num_of_vehicles} scooters, 
                               each with {input_num_of_parts_per_vehicle} connected parts
                               """)
            }
