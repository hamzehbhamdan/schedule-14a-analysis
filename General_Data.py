import streamlit as st
from sched14a import get_sched14a_df
from extractdata import extract_lite_data_gpt
from datetime import datetime, timedelta
import pandas as pd

api_key = "APIKEY"
col_names = {'file': 'File', 'ticker': 'Ticker', 'title': 'Company Name', 'filingDate': 'Filing Date', 'form': 'Form', 'primaryDocDescription': 'Document Description', 'cik': 'CIK', 'accessionNumber': 'Accession Number', 'fileNumber': 'File Number', 'filmNumber': 'Film Number', 'reportDate': 'Report Date'}

def main():
    if "email" not in st.session_state:
        st.session_state.email = ""

    if not st.session_state.email:
        st.session_state.email = st.text_input("Please enter your email (this'll be used to access the SEC's EDGAR Database):", key="email_input")
        st.session_state.submitted = st.button("Submit")

        if st.session_state.email or st.session_state.submitted:
            st.rerun()
    else:
        st.title("Schedule 14A Links Finder")

        st.write("Note that the start and end years refer to the years that the data was filed, which is usually one year after the covered fiscal year.")

        tickers_input = st.text_input("Company Ticker(s), separated by commas", value='CMCSA')

        col1, col2 = st.columns(2)
        years = list(range(2019, datetime.now().year + 1))[::-1]
        with col1:
            start_year = st.selectbox("Start Year", years, index=len(years)-1)
        with col2:
            end_year = st.selectbox("End Year", years, index=0)

        col1, col2 = st.columns(2)
        with col1:
            separate_dfs = st.checkbox('Show Files in Separate Company Dataframes', value=True, key='separate_dfs')
            #ai_data = st.checkbox('Show AI-Generated Metrics and Total Comp', value=False, key='ai_data')
            ai_data = False
        with col2:
            only_links = st.checkbox('Only Show Links in a Dataframe', value=False, key='only_links')
        st.markdown("<p style='font-size: small;'><em>Note that if you check both boxes, only the Links dataframe will show up. Disable the second checkbox to get more data.</em></p>", unsafe_allow_html=True)

        if st.button("Get Schedule 14A Links") or tickers_input:
            if tickers_input:
                tickers = [ticker.strip() for ticker in tickers_input.split(",")]
                email = st.session_state.email
                df = get_sched14a_df(tickers, start_year, end_year, email)
                df.drop(columns=['filmNumber'], inplace=True)

                df.rename(columns={'doc_url': 'file'}, inplace=True)
                df = df[['file'] + [col for col in df.columns if col != 'file']]
                df.rename(columns=col_names, inplace=True)

                df['Summary'] = df['File'].apply(lambda x: x.rsplit('/', 1)[0] + "/R2.htm")

                df = df[['File', 'Summary', 'Ticker', 'Form', 'Filing Date']]

                column_config = {col: {"disabled": True} for col in df.columns}
                column_config["File"] = st.column_config.LinkColumn("File", display_text="🔗 Link", help='Click the link emoji to go to the file.', disabled=True)
                column_config["Summary"] = st.column_config.LinkColumn("Summary", display_text="🔗 Link", help='Click the link emoji to go to the file.', disabled=True)

                if ai_data:
                    df['Year Covered'] = 'NA'
                    df['CEO'] = 'NA'
                    df['Total Compensation'] = 'NA'
                    df['Metrics'] = 'NA'

                    df['Notes'] = df['File'].apply(lambda x: extract_lite_data_gpt(x, api_key=api_key, return_json=True))

                    for idx, row in df.iterrows():
                        data = extract_lite_data_gpt(row['File'], api_key=api_key, return_json=True)
                        lines = []
                        for key, value in data.items():
                            if isinstance(value, list):
                                text_value = ', '.join(map(str, value))
                                line = f"{key}: {text_value}."
                            else:
                                line = f"{key}: {value}."
                            lines.append(line)

                            if 'ceo name' in key.lower():
                                df.at[idx, 'CEO'] = value
                            elif 'year' in key.lower():
                                df.at[idx, 'Year Covered'] = value
                            elif 'metric' in key.lower():
                                df.at[idx, 'Metrics'] = ', '.join(value) if isinstance(value, list) else value
                            elif 'compensation' in key.lower() or 'total' in key.lower():
                                df.at[idx, 'Total Compensation'] = value
                        df.at[idx, 'Notes'] = '\n '.join(lines)

                if only_links == True:
                    st.write("Schedule 14A Links DataFrame:")
                    df['Filing Year'] = pd.to_datetime(df['Filing Date']).dt.year

                    pivot_df = df.copy()
                    pivot_df = pivot_df.pivot(index='Ticker', columns='Filing Year', values='File')
                    pivot_df.reset_index(inplace=True)
                    pivot_df.columns.name = None

                    column_config = {col: {"disabled": True} for col in pivot_df.columns}
                    for year in df['Filing Year'].unique():
                        column_config[str(year)] = st.column_config.LinkColumn(
                            str(year),
                            display_text="🔗 Link",
                            help='Click the link emoji to go to the file.',
                            disabled=True
                        )

                    st.data_editor(
                            pivot_df,
                            column_config=column_config,
                            hide_index=True,
                        )

                else:
                    if separate_dfs == True:
                        for company in tickers:
                            company_df = df[df['Ticker'] == company]
                            st.write(f"DataFrame for {company}:")
                            st.data_editor(
                                company_df,
                                column_config=column_config,
                                hide_index=True,
                            )
                    else:
                        st.write("Schedule 14A Links DataFrame:")
                        st.data_editor(
                            df,
                            column_config=column_config,
                            hide_index=True,
                        )

                    st.markdown("<p style='font-size: small;'><em>If you download the file and open with Excel, you might receive a popup from Excel asking if you'd like to delete leading zeros; select 'no' to avoid it tampering with the company CIK number.</em></p>", unsafe_allow_html=True)

                    df['Filing Date'] = pd.to_datetime(df['Filing Date'])
                    tickers = df['Ticker'].unique()
                    year_range = range(start_year, end_year + 1)
                    missing = {}

                    for ticker in tickers:
                        ticker_df = df[df['Ticker'] == ticker]
                        years_present = ticker_df['Filing Date'].dt.year

                        for year in year_range:
                            count = (years_present == year).sum()
                            if count != 1:
                                if ticker not in missing.keys():
                                    missing[ticker] = {}
                                if count == 0:
                                    missing[ticker][year] = 0
                                else:
                                    missing[ticker][year] = count

                    if missing:                    
                        alerts = []
                        for missing_ticker in missing.keys():
                            years = [str(year) for year in missing[missing_ticker].keys() if missing[missing_ticker][year] == 0]
                            if years:
                                years_text = ', '.join(years)
                                alerts.append(f"* {missing_ticker}: {years_text}")
                        if alerts:
                            alerts_text = "<br>".join(alerts)
                            st.markdown(f"""<span style='color:red;'><i>Alert: The following companies have some missing files: <br>{alerts_text}</i></span>""", unsafe_allow_html=True)
                        
                        alerts = []
                        for missing_ticker in missing.keys():
                            years_text_list = []
                            for year in missing[missing_ticker].keys():
                                if missing[missing_ticker][year] > 1:
                                    years_text_list.append(f"{year} ({missing[missing_ticker][year]} files found)")
                            if years_text_list:
                                years_text = ', '.join(years_text_list)
                                alerts.append(f"* {missing_ticker}: {years_text}")
                        if alerts:
                            alerts_text = "<br>".join(alerts)
                            st.markdown(f"""<span style='color:red;'><i>Alert: The following companies have more than one file per year: <br>{alerts_text}</i></span>""", unsafe_allow_html=True)

            else:
                st.error("Please enter at least one ticker.")

if __name__ == "__main__":
    main()