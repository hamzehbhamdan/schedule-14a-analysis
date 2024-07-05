import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
from PIL import Image
import pytesseract
from io import BytesIO
import re
import faiss
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import tiktoken
from scipy import spatial
import json

pytesseract.pytesseract.tesseract_cmd = 'C:\\Users\\hhamda818@corphq.Comcast.com\AppData\\Local\\Programs\\Tesseract-OCR\\tesseract'

def get_text_and_images(url, headers):
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to retrieve the webpage. Status code: {response.status_code}")
        return None
    soup = BeautifulSoup(response.content, 'html.parser')
    text = soup.get_text(separator='\n', strip=True)
    
    images = []
    for img in soup.find_all('img'):
        src = img.get('src')
        if src:
            img_url = urljoin(url, src)
            images.append(img_url)
            
    tables = []
    for table in soup.find_all('table'):
        if table is not None:
            table_soup = BeautifulSoup(str(table), 'html.parser')
            table_text = table_soup.get_text(separator=' ', strip=True)
            if table_text != '':
                tables.append(table_text)
    
    return text, images, tables

def images_to_text(images_list, headers):
    results = []

    for image_url in images_list:
        response = requests.get(image_url, headers=headers)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))
            text = pytesseract.image_to_string(img)
        else:
            print(f"Failed to retrieve the image. Status code: {response.status_code}")
        if text:
            results.append(text)

    return results

def count_tokens(text, model="gpt-3.5-turbo"):
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

def strings_ranked_by_relatedness(
    query: str,
    df: pd.DataFrame,
    relatedness_fn=lambda x, y: 1 - spatial.distance.cosine(x, y),
    top_n: int = 100,
    api_key: str = "APIKEY"
) -> tuple[list[str], list[float]]:
    """Returns a list of strings and relatednesses, sorted from most related to least."""
    client = OpenAI(api_key=api_key)
    query_embedding_response = client.embeddings.create(
        model="text-embedding-3-large",
        input=query,
    )
    query_embedding = query_embedding_response.data[0].embedding
    strings_and_relatednesses = [
        (row["Text"], relatedness_fn(query_embedding, row["Embeddings"]))
        for i, row in df.iterrows()
    ]
    strings_and_relatednesses.sort(key=lambda x: x[1], reverse=True)
    strings, relatednesses = zip(*strings_and_relatednesses)
    return strings[:top_n], relatednesses[:top_n]

def extract_lite_data_gpt(url, chunk_size=1024, overlap=256, return_json=False, embedding_model='text-embedding-3-large', llm_model='gpt-4o', headers={'User-Agent': 'hamzehhamdan@college.harvard.edu'}, api_key='APIKEY'):
    url = url.rsplit('/', 1)[0] + "/R2.htm"
    result = get_text_and_images(url, headers)
    if result == None:
        return f'ERROR WITH URL {url}'
    else:
        text = result[0]
        images = result[1]
        tables = result[2]

    text = '\n'.join([text_item for text_item in text.split('\n') if bool(re.search(r'\d', text_item))])
    tables= [table for table in tables if bool(re.search(r'\d', table) and not re.search(r'\b2024\b|\b20\s24\b', table))]

    all_data = " ".join(text.split('\n') + (tables))

    client = OpenAI(api_key=api_key)
    text = all_data.replace("\n", " ")

    query_text = f"""What were the bonus targets for the company? This is often reported in some financial metric for the company like EBITDA, Revenue, FCF, but can include other company-specific metrics.

    I would like you to return the following data from the proxy statement above.

    CEO name:
    Year covered:

    Names of metrics used to evaluate performance.

    Total CEO Compensation $:

    Refrain from making any calculations. Only report what is found in the report; if something is not in the report, write NA."""

    conversation = [
        {"role": "system", "content": """You are an expert financial analyst. Your task is to help me analyze Schedule 14A files and piece together executive compensation. Return your answer in JSON format return it as a JSON object:
        
        **CEO name**
        **Year covered**
        **Names of metrics used to evaluate performance**
        **Total CEO Compensation $**

        If any information is not found in the provided text, mark it as "NA". Please do not start your response with "json", and instead just return the dictionary. Please only return the data for the CEO."""},
        {"role": "user", "content": "Query: " + query_text + "\n Relevant texts:" + all_data}
    ]

    simplified_request = client.chat.completions.create(
        model=llm_model,
        messages=conversation,
        temperature=0.2,
        max_tokens=300,
        top_p=0.2
    )
    
    try:
        structured_data = simplified_request.choices[0].message.content.strip()
        structured_dict = json.loads(structured_data)
        return structured_dict
    except Exception as e:
        print(f'Initial attempt failed: {e}')       

    reformat_conversation = [
        {"role": "system", "content": """You are an expert computer scientiest. Your task is to help me extract the following data in JSON format. Return your answer in JSON format return it as a JSON object:
        
        **CEO name**
        **Year covered**
        **Names of metrics used to evaluate performance**
        **Total CEO Compensation $**

        If any information is not found in the provided text, mark it as "NA". Please do not start your response with "json", and instead just return the dictionary."""},
        {"role": "user", "content": "Data:" + simplified_request.choices[0].message.content.strip()}
    ]

    while attempts < 5:
        try:
            simplified_request = client.chat.completions.create(
                model="gpt-3.5-turbo-0125",
                messages=reformat_conversation,
                max_tokens=200,
                n=1,
                stop=None,
                temperature=0.7,
            )

            structured_data = simplified_request.choices[0].message.content.strip()
            structured_dict = json.loads(structured_data)
            return structured_dict

        except Exception as e:
            print(f'Attempt {attempts + 1} failed: {e}')
            attempts += 1

    simplified_request = client.chat.completions.create(
        model="gpt-3.5-turbo-0125",
        messages=conversation,
        max_tokens=200,
        n=1,
        stop=None,
        temperature=0.2,
    )

    structured_data = simplified_request.choices[0].message.content.strip()
    return structured_data

def extract_full_data_gpt(url, chunk_size=1024, overlap=256, embedding_model='text-embedding-3-large', llm_model='gpt-4o', single_shot=True, headers={'User-Agent': 'hamzehhamdan@college.harvard.edu'}, api_key='APIKEY'):
    result = get_text_and_images(url, headers)
    if result == None:
        return f'ERROR WITH URL {url}'
    else:
        text = result[0]
        images = result[1]
        tables = result[2]

    text = '\n'.join([text_item for text_item in text.split('\n') if bool(re.search(r'\d', text_item))])
    tables= [table for table in tables if bool(re.search(r'\d', table) and not re.search(r'\b2024\b|\b20\s24\b', table))]

    all_data = " ".join(text.split('\n') + (tables))

    client = OpenAI(api_key=api_key)
    text = all_data.replace("\n", " ")
    text_chunks = []
    start_idx = 0

    while start_idx < len(text):
        end_idx = min(start_idx + chunk_size, len(text))
        text_chunks.append(text[start_idx:end_idx])
        start_idx += chunk_size - overlap

    embeddings = [client.embeddings.create(input = [text_piece], model=embedding_model).data[0].embedding for text_piece in text_chunks]

    df = pd.DataFrame({
        'Text': text_chunks,
        'Embeddings': embeddings
    })

    if single_shot==True:
        query_text = f"""What were the bonus targets for the company? This is often reported in some financial metric for the company like EBITDA, Revenue, FCF, but can include other company-specific metrics.

        I would like you to return the following data from the proxy statement above.

        CEO name:
        Year covered:

        Bonus Weight from Financial Metrics (total, with a breakdown with each metric):
        Bonus Weight Non-Financial:

        Proxy Target for each metric (single value, in dollars).
        Proxy Actual for each metric (single value, in dollars).
        Financial Achievement Percentage for each metric.

        Financial-Metric Achievement % (one value):
        Non-Financial Achievement % (one value):

        Bonus Payout $:
        Total Compensation $:

        Refrain from making any calculations. Only report what is found in the report; if something is not in the report, write NA. Please only return the data for the CEO."""

        strings, relatednesses = strings_ranked_by_relatedness(query_text, df, top_n=100)

        conversation = [
            {"role": "system", "content": "You are an expert financial analyst. Your task is to help me analyze Schedule 14A files and piece together executive compensation."},
            {"role": "user", "content": "Query: " + query_text + "\n Relevant texts:" + ' '.join(strings)}
        ]

        completion = client.chat.completions.create(
            model=llm_model,
            messages=conversation,
            temperature=0.2,
            max_tokens=700,
            top_p=0.2
        )

        return completion.choices[0].message.content
    else:
        query_text_1 = """What were the metrics used for the bonus targets for the company? This is often reported in some financial metric for the company like EBITDA, Revenue, FCF, but can include other company-specific metrics.

        The metrics are usually reported in the following sections:

        CEO name:
        Year covered:

        Bonus Weight from Financial Metrics:
        Bonus Weight Non-Financial:

        Proxy Target for each metric (single value, in dollars).
        Proxy Actual for each metric (single value, in dollars).

        Financial-Metric Achievement % (one value):
        Non-Financial Achievement % (one value):

        Bonus Payout $:
        Total Compensation $:

        Please only return the names of the metrics used. You should also consolidate them (i.e. FCF and Adjusted FCF should be in one category). Your response should be one sentence with comma separated metrics."""

        strings, relatednesses = strings_ranked_by_relatedness(query_text_1, df, top_n=50)

        conversation_1 = [
            {"role": "system", "content": "You are an expert financial analyst. Your task is to help me analyze Schedule 14A files and piece together executive compensation. Your goal is to return the metrics used for determining the bonus of the CEO. There should be 2-4 of them."},
            {"role": "user", "content": "Query: " + query_text_1 + "\n Relevant texts:" + " ".join(strings)}
        ]

        completion_1 = client.chat.completions.create(
            model=llm_model,
            messages=conversation_1,
            temperature=0.2,
            max_tokens=40,
            top_p=0.2
        )

        conversation_2 = [
            {"role": "system", "content": "You are an expert financial analyst. Your task is to help me analyze Schedule 14A files and piece together executive compensation. Your goal is to extract data."},
            {"role": "user", "content": f"Query: For each of these metrics {completion_1.choices[0].message.content}, please give me the proxy target and actual values. Keep your response as short as possible." + "\n Relevant texts:" + ' '.join(strings)}
        ]

        completion_2 = client.chat.completions.create(
            model=llm_model,
            messages=conversation_2,
            temperature=0.2,
            max_tokens=200,
            top_p=0.2
        )

        query_text_3 = """Looking at the executive compensation data, please fill out the data below:

        CEO name:
        Year covered:

        Bonus Weight from Financial Metrics:
        Bonus Weight Non-Financial:

        Achievement percentage of financial metrics in bonus calculation:
        Achievement percentage of non-financial metrics in bonus calculation:

        Bonus Payout $:
        Total Compensation $:

        Refrain from making any calculations. Only report what is found in the report; if something is not in the report, write NA."""

        conversation_3 = [
            {"role": "system", "content": "You are an expert financial analyst. Your task is to help me analyze Schedule 14A files and piece together executive compensation. Your goal is to extract data."},
            {"role": "user", "content": f"Query {query_text_3}" + "\n Relevant texts:" + ' '.join(strings)}
        ]

        completion_3 = client.chat.completions.create(
            model=llm_model,
            messages=conversation_3,
            temperature=0.2,
            max_tokens=450,
            top_p=0.2
        )

        print(completion_3.choices[0].message.content)

        return completion_1.choices[0].message.content, completion_2.choices[0].message.content, completion_3.choices[0].message.content