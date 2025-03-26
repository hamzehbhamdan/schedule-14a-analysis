# Schedule 14a Analysis

## General Information

This Streamlit app fetches Schedule 14a filings (Proxy Statements) for any company with a registered stock ticker with a filing date from 2019 to 2025. Proxy Statements are typically very long documents used for analyzing executive compensation, including salaries, bonuses, and incentive programs. 

## Page Descriptions

### Main Page

The main page gives the link to the documents, as well as a link to a summary section that typically includes information on executive compensation (available for more recent documents).

### AI Summarizer

The AI summarizer section takes in an OpenAI API Key and runs an editable preset prompt that extracts information on the structure of the compensation programs. Note that this can be a bit quite slow—I developed this as a project then decided that a chatbot would be more helpful.

## Demo

View a live demo [here](https://schedule-14a-analysis.streamlit.app/).
