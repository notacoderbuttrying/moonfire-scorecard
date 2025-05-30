"""
Golden-Triangle Scorecard
Rank European seed-stage AI/Web3 startups based on Moonfire Ventures' three pillars:
ACCESS (language/locale support), EFFICIENCY (capital raised/employee count), and SERVICE QUALITY (ratings)

Install dependencies: pip install streamlit pandas plotly scikit-learn st_aggrid
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from st_aggrid import AgGrid, GridOptionsBuilder
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from datetime import datetime

def main():
    st.title("Golden-Triangle Scorecard")
    st.markdown("""
    Rank European seed-stage AI/Web3 startups based on Moonfire Ventures' three pillars:
    - ACCESS: Number of languages/locales supported
    - EFFICIENCY: Total capital raised USD ÷ current employee count
    - SERVICE QUALITY: Average rating from G2 or Capterra
    """)

    # Sidebar with file uploader
    st.sidebar.header("Upload Data")
    uploaded_file = st.sidebar.file_uploader("Choose a CSV file", type="csv")
    
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_csv("deals.csv")

    # Process data
    try:
        # Get unique companies and their total funding
        companies = df.groupby('results__funded_organization_identifier__uuid').agg({
            'results__funded_organization_identifier__value': 'first',  # company name
            'results__money_raised__value_usd': 'sum'  # total raised
        }).reset_index()
        
        companies.columns = ['uuid', 'company', 'raised_usd']
        
        # Add default values
        companies['employees'] = 1  # Default to 1 to avoid division by zero
        companies['languages'] = 0  # Default to 0 languages
        companies['rating'] = 0  # Default to 0 rating
        
        # Calculate pillar scores
        companies['efficiency'] = companies['raised_usd'] / companies['employees']
        
        # Scale scores to 0-100
        scaler = MinMaxScaler(feature_range=(0, 100))
        companies['access_score'] = scaler.fit_transform(companies[['languages']])
        companies['efficiency_score'] = scaler.fit_transform(companies[['efficiency']])
        companies['service_quality_score'] = companies['rating']
        
        # Calculate overall score
        companies['overall_score'] = companies[['access_score', 'efficiency_score', 'service_quality_score']].mean(axis=1)
        companies['moonfire_rank'] = companies['overall_score'].rank(ascending=False)
        
        # Create scatter plot
        fig = px.scatter(
            companies,
            x='languages',
            y='efficiency',
            size='service_quality_score',
            hover_data=['company', 'access_score', 'efficiency_score', 'service_quality_score'],
            title="Golden-Triangle Scorecard Visualization"
        )
        st.plotly_chart(fig)

        # Create Ag-Grid table
        gb = GridOptionsBuilder.from_dataframe(companies)
        gb.configure_pagination()
        gb.configure_default_column(editable=False, groupable=True)
        gb.configure_column("company", header_name="Company")
        gb.configure_column("access_score", header_name="ACCESS Score")
        gb.configure_column("efficiency_score", header_name="EFFICIENCY Score")
        gb.configure_column("service_quality_score", header_name="SERVICE QUALITY Score")
        gb.configure_column("overall_score", header_name="Overall Score")
        gb.configure_column("moonfire_rank", header_name="Moonfire Rank")
        
        gridOptions = gb.build()
        
        # Add star emoji for top 20
        companies['moonfire_rank'] = companies['moonfire_rank'].apply(
            lambda x: f"⭐ {x}" if x <= 20 else str(int(x))
        )
        
        AgGrid(companies, gridOptions=gridOptions)

        # Download button
        csv = companies.to_csv(index=False)
        st.download_button(
            "Download Scorecard",
            csv,
            f"moonfire_scorecard_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv",
            key='download-csv'
        )

        # Expanders
        with st.expander("Methodology"):
            st.markdown("""
            The Golden-Triangle Scorecard evaluates startups based on three pillars:
            
            1. ACCESS: Number of languages/locales supported (scaled 0-100)
            2. EFFICIENCY: Capital raised USD ÷ employee count (scaled 0-100)
            3. SERVICE QUALITY: Average rating from G2 or Capterra (raw score)
            
            Scores are normalized to a 0-100 scale and averaged to determine the overall score.
            """)

        with st.expander("Caveats/Next Steps"):
            st.markdown("""
            - This is a simplified version using only the CSV data
            - Future improvements: Add web scraping for language and rating data
            - Currently using default values for languages and ratings
            """)

    except Exception as e:
        st.error(f"Error processing data: {str(e)}")

if __name__ == "__main__":
    main()
