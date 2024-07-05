# Some code adapted from GGRusty
# https://github.com/GGRusty/Edgar_Video_content/blob/main/Part_4/edgar_functions.py

import requests
import logging
import calendar
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from ratelimiter import RateLimiter

rate_limiter = RateLimiter(10, 1)
s = requests.Session()

pd.options.display.float_format = (lambda x: "{:,.0f}".format(x) if int(x)==x else "{:,.2f}".format(x))

statement_keys_map = {
    "balance_sheet": [
        "balance sheet",
        "balance sheets",
        "statement of financial position",
        "consolidated balance sheets",
        "consolidated balance sheet",
        "consolidated financial position",
        "consolidated balance sheets - southern",
        "consolidated statements of financial position",
        "consolidated statement of financial position",
        "consolidated statements of financial condition",
        "combined and consolidated balance sheet",
        "condensed consolidated balance sheets",
        "consolidated balance sheets, as of december 31",
        "dow consolidated balance sheets",
        "consolidated balance sheets (unaudited)",
        "balance sheets (parenthetical)",
    ],
    "income_statement": [
        "income statement",
        "income statements",
        "statement of earnings (loss)",
        "statements of consolidated income",
        "consolidated statements of operations",
        "consolidated statement of operations",
        "consolidated statements of earnings",
        "consolidated statement of earnings",
        "consolidated statements of income",
        "consolidated statement of income",
        "consolidated income statements",
        "consolidated income statement",
        "condensed consolidated statements of earnings",
        "consolidated results of operations",
        "consolidated statements of income (loss)",
        "consolidated statements of income - southern",
        "consolidated statements of operations and comprehensive income",
        "consolidated statements of comprehensive income",
        "statements of operations",
    ],
    "cash_flow_statement": [
        "cash flows statement",
        "cash flows statements",
        "statement of cash flows",
        "statements of cash flows",
        "statements of consolidated cash flows",
        "consolidated statements of cash flows",
        "consolidated statement of cash flows",
        "consolidated statement of cash flow",
        "consolidated cash flows statements",
        "consolidated cash flow statements",
        "condensed consolidated statements of cash flows",
        "consolidated statements of cash flows (unaudited)",
        "consolidated statements of cash flows - southern",
    ],
}

def get_companyIdentifiers(headers):
    companyTickers = requests.get('https://www.sec.gov/files/company_tickers.json', headers=headers)
    companyIdentifiers = pd.DataFrame.from_dict(companyTickers.json(), orient='index')
    companyIdentifiers['cik_str'] = companyIdentifiers['cik_str'].astype(str).str.zfill(10)
    return companyIdentifiers

def get_cik(ticker, companyIdentifiers):
    filtered_df = companyIdentifiers[companyIdentifiers['ticker'] == ticker]
    if not filtered_df.empty:
        return filtered_df['cik_str'].values[0]
    else:
        return None

def get_submissionMetadata(headers, cik):
    if cik==None:
        return None
    submissionMetadata = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=headers)
    submissionMetadata.raise_for_status()
    return submissionMetadata.json()

def get_allForms(submissionMetadata):
    if submissionMetadata==None:
        return None
    return pd.DataFrame(submissionMetadata['filings']['recent'])

def get_formAccessionNumbers(allForms, form):
    if allForms is None or allForms.empty:
        return None
    df = allForms[allForms['form'] == form][['reportDate', 'accessionNumber']]
    df = df.set_index(['reportDate'])
    return df

def get_recentFormAccession(allForms, form):
    return allForms[allForms['form'] == form]['accessionNumber'].iloc[0]

def get_documentLink(allForms, form):
    if allForms is None or allForms.empty:
        return None
    filtered_df = allForms[allForms['form'] == form]
    if not filtered_df.empty:
        return filtered_df['primaryDocument'].iloc[0]
    else:
        return None

def _get_file_name(report):
    html_file_name_tag = report.find('HtmlFileName')
    xml_file_name_tag = report.find('XmlFileName')

    if html_file_name_tag:
        return html_file_name_tag.text
    elif xml_file_name_tag:
        return xml_file_name_tag.text
    else:
        return ""

def _is_statement_file(short_name_tag, long_name_tag, file_name):
    return (short_name_tag is not None and long_name_tag is not None and file_name and "Statement" in long_name_tag.text)

def _get_financialStatementDataFileStructure(headers, cik, formAccessionNumber):
    try:
        session = requests.Session()
        cik_url, accession_url = cik.lstrip('0'), formAccessionNumber.replace('-', '')
        base_link = f'https://www.sec.gov/Archives/edgar/data/{cik_url}/{accession_url}'
        filing_summary_link = f'{base_link}/FilingSummary.xml'
        filing_summary_response = session.get(filing_summary_link, headers=headers).content.decode('utf-8')

        filing_summary_soup = BeautifulSoup(filing_summary_response, 'lxml-xml')
        statement_file_names_dict = {}

        for report in filing_summary_soup.find_all('Report'):
            file_name = _get_file_name(report)
            short_name, long_name = report.find('ShortName'), report.find('LongName')

            if _is_statement_file(short_name, long_name, file_name):
                statement_file_names_dict[short_name.text.lower()] = file_name
        return statement_file_names_dict
    
    except requests.RequestException as e:
        print(f"An error occurred while fetching financial statement data: {e}")
        return {}

def _get_financialStatementSoup(headers, cik, statement_name, formAccessionNumber, statement_keys_map):
    '''
    statement name should be one of 'balance_sheet', 'income_statement', or 'cash_flow_statement'
    '''
    session = requests.Session()

    base_link = f'https://www.sec.gov/Archives/edgar/data/{cik}/{formAccessionNumber}'
    statemet_file_name_dict = _get_financialStatementDataFileStructure(headers, cik, formAccessionNumber)
    statement_link = None

    for possible_key in statement_keys_map.get(statement_name.lower(), []):
        file_name = statemet_file_name_dict.get(possible_key.lower())
        if file_name:
            statement_link = f'{base_link}/{file_name}'
            break

    if not statement_link:
        raise ValueError(f'Could not find statement file name for {statement_name}')
    
    try:
        statement_response = session.get(statement_link, headers=headers)
        statement_response.raise_for_status()
        if statement_link.endswith('.xml'):
            return BeautifulSoup(statement_response.content, 'lxml-xml', from_encoding='utf-8')
        else:
            return BeautifulSoup(statement_response.content, 'lxml')
        
    except requests.RequestException as e:
        raise ValueError(f"Error fetching the statement: {e}")
    
def _standardize_date(date):
    for abbr, full in zip(calendar.month_abbr[1:], calendar.month_name[1:]):
        date = date.replace(abbr, full)
    return date

def _get_statementDates(soup):
    table_headers = soup.find_all('th', {'class': 'th'})
    dates = [str(th.div.string) for th in table_headers if th.div and th.div.string]
    dates = [_standardize_date(date).replace('.', '') for date in dates]
    index_dates = pd.to_datetime(dates)
    return index_dates

def _keep_numbers_and_decimals_only_in_string(mixed_string):
    num = '1234567890.'
    allowed = list(filter(lambda x: x in num, mixed_string))
    return ''.join(allowed)

def _get_statementData(soup):
    columns = []
    values_set = []
    date_time_index = _get_statementDates(soup)

    for table in soup.find_all('table'):
        unit_multiplier = 1
        special_case = False

        table_header = table.find('th')
        if table_header:
            header_text = table_header.get_text()
            if 'in Thousands' in header_text:
                unit_multiplier = 1
            elif 'in Millions' in header_text:
                unit_multiplier = 1000
            if 'unless otherwise specified' in header_text:
                special_case = True
        
        for row in table.select('tr'):
            onclick_elements = row.select('td.pl a, td.pl.custom a')
            if not onclick_elements:
                continue

            onclick_attr = onclick_elements[0]['onclick']
            column_title = onclick_attr.split('defref_')[-1].split("',")[0]
            columns.append(column_title)

            values = [np.NaN] * len(date_time_index)

            for i, cell in enumerate(row.select('td.text, td.nump, td.num')):
                if 'text' in cell.get('class'):
                    continue

                value = _keep_numbers_and_decimals_only_in_string(cell.text.replace('$', '').replace(',', '').replace('(', '').replace(')', '').strip())

                if value:
                    value = float(value)
                    if special_case:
                        value /= 1000
                    else:
                        if 'nump' in cell.get('class'):
                            values[i] = value * unit_multiplier
                        else:
                            values[i] = -value * unit_multiplier
            
            values_set.append(values)
    
    return columns, values_set, date_time_index

def get_statementDF(headers, cik, statement_name, formAccessionNumber, statement_keys_map):
    formAccessionNumber = formAccessionNumber.replace('-', '')
    try:
        soup = _get_financialStatementSoup(headers, cik, statement_name, formAccessionNumber, statement_keys_map)
    except Exception as e:
        logging.error(f'Failed to get statement soup: {e} for accession number: {formAccessionNumber}')
        return None
    
    if soup:
        try:
            columns, values_set, date_time_index = _get_statementData(soup)
            transposed_values_set = list(zip(*values_set))
            df = pd.DataFrame(transposed_values_set, columns=columns, index=date_time_index)

            if not df.empty:
                df = df.T.drop_duplicates()
            else:
                logging.warning(f'Empty DataFrame for accession number: {formAccessionNumber}')
                return None
            return df
        except Exception as e:
            logging.error(f'Error processing statement: {e}')
            return None

def get_companyFactsData(headers, cik):
    companyFacts = requests.get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json', headers=headers)
    return companyFacts.json()

def get_companyFactsDataFrame(headers, cik):
    companyFacts = get_companyFactsData(headers, cik)
    us_gaap_data = companyFacts['facts']['us-gaap']
    df_data = []
    for fact, details in us_gaap_data.items():
        for unit in details['units']:
            for item in details['units'][unit]:
                row = item.copy()
                row['fact'] = fact
                df_data.append(row)
    
    df = pd.DataFrame(df_data)
    df['end'] = pd.to_datetime(df['end'])
    df['start'] = pd.to_datetime(df['start'])
    df = df.drop_duplicates(subset=['fact', 'end', 'val'])
    df.set_index('end', inplace=True)
    labels_dict = {fact: details['label'] for fact, details in us_gaap_data.items()}
    return df, labels_dict

def get_annualFacts(headers, cik, allForms):
    accession_data = get_formAccessionNumbers(allForms, '10-K')['accessionNumber']
    df, label_dict = get_companyFactsDataFrame(headers, cik)
    ten_k = df[df['accn'].isin(accession_data)]
    ten_k = ten_k[ten_k.index.isin(accession_data.index)]
    pivot = ten_k.pivot_table(values='val', columns='fact', index='end')
    pivot.rename(columns=label_dict, inplace=True)
    return pivot.T

def get_quarterlyFacts(headers, cik, allForms):
    accession_data = get_formAccessionNumbers(allForms, '10-Q')['accessionNumber']
    df, label_dict = get_companyFactsDataFrame(headers, cik)
    ten_q = df[df['accn'].isin(accession_data)]
    ten_q = ten_q[ten_q.index.isin(accession_data.index)]
    pivot = ten_q.pivot_table(values='val', columns='fact', index='end')
    pivot.rename(columns=label_dict, inplace=True)
    return pivot.T

def get_companyConcept(headers, cik):
    companyConcept = requests.get((f'https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}' f'/us-gaap/Assets.json'), headers=headers)
    return pd.DataFrame.from_dict((companyConcept.json()['units']['USD']))    

def get_companyData(headers, ticker, form, companyIdentifiers):
    rate_limiter.wait()
    cik = get_cik(ticker=ticker, companyIdentifiers=companyIdentifiers)
    submissionMetadata = get_submissionMetadata(headers=headers, cik=cik)
    allForms = get_allForms(submissionMetadata=submissionMetadata)
    formAccessionNumber = get_recentFormAccession(allForms=allForms, form=form)

    # Get document data
    balanceSheet = get_statementDF(headers, cik, 'balance_sheet', formAccessionNumber, statement_keys_map)         
    incomeStatement = get_statementDF(headers, cik, 'income_statement', formAccessionNumber, statement_keys_map)         
    cashFlowStatement = get_statementDF(headers, cik, 'cash_flow_statement', formAccessionNumber, statement_keys_map) 
    documentData = {'Balance Sheet': balanceSheet, 'Income Statement': incomeStatement, 'Cash Flow Statement': cashFlowStatement}        

    # Get financial indicators reported
    rate_limiter.wait()
    companyFactsDF = get_companyFactsDataFrame(headers=headers, cik=cik)[0]

    # Get annual and quarterly facts
    annualFactsDF = get_annualFacts(headers, cik, allForms)
    quarterlyFactsDF = get_quarterlyFacts(headers, cik, allForms)

    # Get XBRL disclosures, assets data
    rate_limiter.wait()
    assetsData = get_companyConcept(headers=headers, cik=cik)

    get_documentText(headers, cik, form, formAccessionNumber, allForms)
    return {'Company Facts': companyFactsDF, 'Annual Financial Facts': annualFactsDF, 'Quarterly Financial Facts': quarterlyFactsDF, '10K Data': documentData, 'Assets Data': assetsData}

def get_documentText(headers, cik, form, formAccessionNumber, allForms):
    # TODO: doesn't work well for DJT, doesn't even pick up colomn ids for TSLA
    session = requests.Session()
    doc_link = get_documentLink(allForms, form)
    formAccessionNumber = formAccessionNumber.replace('-', '')
    base_link = f'https://www.sec.gov/Archives/edgar/data/{cik}/{formAccessionNumber}/{doc_link}'
    response = requests.get(base_link, headers=headers)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        toc_element = soup.find(lambda tag: (tag.name == "div" or tag.name == "span") and "TABLE OF CONTENTS" in tag.text)

        column_values = []
        column_titles = []
        column_ids = []
        data = {}

        if toc_element:
            # Approach to find the first <table> after the TOC element
            next_elem = toc_element.find_next()  # Get the next element
            while next_elem:
                if next_elem.name == 'table':
                    # Found the table, process it here
                    rows = next_elem.find_all('tr')
                    for row in rows:
                        columns = row.find_all('td')
                        if len(columns) >= 2:
                            if columns[0].text.strip() != '' and "part" not in columns[0].text.strip().lower():
                                column_values.append(columns[0].text.strip())
                                column_titles.append(columns[1].text.strip())
                                a_tags = columns[1].find_all('a')
                                for a_tag in a_tags:
                                    if a_tag.has_attr('href'):
                                        column_ids.append(a_tag['href'].strip().replace('#', ''))

                next_elem = next_elem.find_next()  # Move to the next element in the document

        # TODO: this doesn't work. instead, use the ids in the table of contents links to save the data between links
        # we alsready have the titles saved in column_titles

        for i, column_id in enumerate(column_ids):
            if i + 1 < len(column_ids):
                start_id = soup.find(id=column_id)
                end_id = soup.find(id=column_ids[i+1])
                if start_id and end_id:
                    content = ''
                    for elem in start_id.find_next_siblings():
                        if elem == end_id:
                            break
                        content += str(elem)
                    data[column_ids[i]] = BeautifulSoup(content, 'html.parser').get_text(separator=" ", strip=True)
                else:
                    print(f'ID {column_id} not found.')
            else:
                start_id = soup.find(id=column_id)
                if start_id:
                    content = ''.join(str(elem) for elem in start_id.find_next_siblings())
                    data[column_ids[i]] = BeautifulSoup(content, 'html.parser').get_text(separator=" ", strip=True)

    else:
        print(f'Failed to retreive document {formAccessionNumber}')
        return ""