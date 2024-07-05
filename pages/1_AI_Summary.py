import streamlit as st
from sched14a import get_sched14a_df
from extractdata import extract_full_data_gpt
from datetime import datetime

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
        st.title("AI Generated Summary")
        st.write("Note that the year refers to the year that the data was filed, which is usually one year after the covered fiscal year.")

        col1, col2 = st.columns(2)
        years = list(range(2019, datetime.now().year + 1))[::-1]
        with col1:
            tickers_input = st.text_input("Company Ticker", value='CMCSA')
        with col2:
            year = st.selectbox("Year Filed", years, index=0)
        api_key = st.text_input("OpenAI API Key").strip()
        query = st.text_area("ChatGPT Request", value=f"""What were the bonus targets for the company? This is often reported in some financial metric for the company like EBITDA, Revenue, FCF, but can include other company-specific metrics.

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

Refrain from making any calculations. Only report what is found in the report; if something is not in the report, write NA. Please only return the data for the CEO.""")

        if st.button("Get Schedule 14A Links"):
            if not api_key:
                st.error("Please enter your OpenAI Key.")
            elif tickers_input:
                tickers = [ticker.strip() for ticker in tickers_input.split(",")]
                email = st.session_state.email
                df = get_sched14a_df(tickers, year, year, email)
                df.drop(columns=['filmNumber'], inplace=True)

                df.rename(columns={'doc_url': 'file'}, inplace=True)
                df = df[['file'] + [col for col in df.columns if col != 'file']]
                df.rename(columns=col_names, inplace=True)

                df['Summary'] = df['File'].apply(lambda x: x.rsplit('/', 1)[0] + "/R2.htm")

                df = df[['File', 'Summary', 'Ticker', 'Form', 'Filing Date']]

                column_config = {col: {"disabled": True} for col in df.columns}
                column_config["File"] = st.column_config.LinkColumn("File", display_text="🔗 Link", help='Click the link emoji to go to the file.', disabled=True)
                column_config["Summary"] = st.column_config.LinkColumn("Summary", display_text="🔗 Link", help='Click the link emoji to go to the file.', disabled=True)

                st.write("Schedule 14A Links DataFrame:")
                st.data_editor(
                    df,
                    column_config=column_config,
                    hide_index=True,
                )

                st.write('Generating an AI summary of the file above. This may take a few minutes.')

                data = extract_full_data_gpt(df.loc[0, 'File'], query=query, api_key=api_key)
                st.markdown(data)

            else:
                st.error("Please enter at least one ticker.")

if __name__ == "__main__":
    main()
