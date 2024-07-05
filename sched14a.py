from ratelimiter import RateLimiter
from edgar import *
from extractdata import get_text_and_images

rate_limiter = RateLimiter(10, 1)
s = requests.Session()

pd.options.display.float_format = (lambda x: "{:,.0f}".format(x) if int(x)==x else "{:,.2f}".format(x))

def get_sched14a_df(tickers, start_year, end_year, email):
    tickers = [ticker.upper() for ticker in tickers]
    headers = {'User-Agent': email}
    identifiers = get_companyIdentifiers(headers=headers)
    tickers_data = identifiers[identifiers['ticker'].isin(tickers)]

    exec_comp_form_data = []

    for ticker in tickers_data['ticker'].tolist():
        company_data = get_allForms(get_submissionMetadata(headers=headers, cik=get_cik(ticker=ticker, companyIdentifiers=tickers_data)))

        descriptions = ['DEF 14A', 'PREC14A', 'FORM DEF 14A', 'FORM PREC14A', 'DEFINITIVE PROXY STATEMENT']
        pattern = '|'.join(descriptions)
        exec_comp = company_data[company_data['form'].str.contains('14A', na=False) & company_data['primaryDocDescription'].str.contains(pattern, na=False)]

        exec_comp.loc[:, 'filingDate'] = pd.to_datetime(exec_comp['filingDate'], errors='coerce').dt.date
        exec_comp.loc[:, 'reportDate'] = pd.to_datetime(exec_comp['reportDate'], errors='coerce').dt.date

        exec_comp_sorted = exec_comp.sort_values(by='filingDate', ascending=False)

        exec_comp_sorted['filingDate'] = pd.to_datetime(exec_comp_sorted['filingDate'], errors='coerce')
        filtered_df = exec_comp_sorted[(exec_comp_sorted['filingDate'].notnull()) & (exec_comp_sorted['filingDate'].dt.year.between(start_year, end_year))]

        if not filtered_df.empty:
            most_recent_report = filtered_df.copy()
            for idx, row in most_recent_report.iterrows():
                row['ticker'] = ticker
                row['title'] = tickers_data[tickers_data['ticker'] == ticker]['title'].values[0]
                row['cik'] = tickers_data[tickers_data['ticker'] == ticker]['cik_str'].values[0]

                cik = row['cik']
                accession_number = row['accessionNumber'].replace('-','')
                primary_document_link = row['primaryDocument']
                
                row['doc_url'] = f'https://www.sec.gov/Archives/edgar/data/{cik}/{accession_number}/{primary_document_link}'
                exec_comp_form_data.append(row.to_dict())

    exec_comp_forms_df = pd.DataFrame(exec_comp_form_data)
    column_order = ['ticker', 'title', 'form', 'filingDate', 'primaryDocDescription', 'doc_url', 'cik', 'accessionNumber', 'fileNumber', 'filmNumber', 'reportDate']

    exec_comp_forms_df['filingDate'] = pd.to_datetime(exec_comp_forms_df['filingDate'], errors='coerce')
    exec_comp_forms_df['reportDate'] = pd.to_datetime(exec_comp_forms_df['reportDate'], errors='coerce')
    exec_comp_forms_df['filingDate'] = exec_comp_forms_df['filingDate'].dt.date
    exec_comp_forms_df['reportDate'] = exec_comp_forms_df['reportDate'].dt.date

    exec_comp_forms_df = exec_comp_forms_df.reindex(columns=column_order)

    return exec_comp_forms_df

def extract_text(exec_comp_forms_df, email):
    headers = {'User-Agent': email}

    links = exec_comp_forms_df['doc_url'].tolist()
    tickers = exec_comp_forms_df['ticker'].tolist()

    data = {}

    for idx, link in enumerate(links):
        text, images, tables = get_text_and_images(link, headers)
        text = text.split('Washington, D.C. 20549')[1]
        data[tickers[idx]] = {'Text': text, 'Images': images, 'Tables': tables}
    
    return data
