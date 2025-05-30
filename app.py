"""
Golden-Triangle Scorecard
Rank European seed-stage AI/Web3 startups based on Moonfire Ventures' three pillars:
ACCESS (language/locale support), EFFICIENCY (capital raised/employee count), and SERVICE QUALITY (ratings)

Install dependencies: pip install streamlit pandas plotly scikit-learn st_aggrid beautifulsoup4 duckduckgo-search
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from st_aggrid import AgGrid, GridOptionsBuilder
import numpy as np
from sklearn.preprocessing import MinMaxScaler
import duckduckgo_search
from bs4 import BeautifulSoup
import requests
import json
import os
from datetime import datetime

# Cache directory for web scraping results
cache_dir = "cache"
os.makedirs(cache_dir, exist_ok=True)

def get_cache_key(company_name):
    return os.path.join(cache_dir, f"{company_name.replace(' ', '_')}.json")

def fetch_company_data(company_name, website_url):
    """Fetch language support and ratings data for a company"""
    cache_file = get_cache_key(company_name)
    
    # Check cache first
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            return json.load(f)
    
    try:
        # Search for company website
        results = duckduckgo_search.search(f"site:{website_url} languages supported", max_results=1)
        if results:
            url = results[0]['href']
            response = requests.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for language/locale indicators
            langs = []
            for lang in soup.find_all('html', {'lang': True}):
                langs.append(lang['lang'])
            for meta in soup.find_all('meta', {'content': True}):
                if 'language' in meta.get('name', '').lower():
                    langs.extend(meta['content'].split(','))
            
            # Search for ratings
            rating = "N/A"
            g2_results = duckduckgo_search.search(f"{company_name} G2 rating", max_results=1)
            if g2_results:
                rating_url = g2_results[0]['href']
                rating_response = requests.get(rating_url)
                rating_soup = BeautifulSoup(rating_response.text, 'html.parser')
                rating_el = rating_soup.find('span', {'class': 'rating-value'})
                if rating_el:
                    rating = float(rating_el.text.strip())
    except Exception as e:
        print(f"Error fetching data for {company_name}: {e}")
    
    # Default values if no data found
    data = {
        'languages': len(set(langs)),
        'rating': rating
    }
    
    # Save to cache
    with open(cache_file, 'w') as f:
        json.dump(data, f)
    
    return data

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
        # Default to deals.csv
        df = pd.read_csv("deals.csv")

    # Process data
    try:
        # Transform the funding rounds data to get company-level information
        companies = df.groupby('results__funded_organization_identifier__uuid').agg({
            'results__funded_organization_identifier__value': 'first',  # company name
            'results__funded_organization_identifier__permalink': 'first',  # website URL
            'results__money_raised__value_usd': 'sum',  # total raised
            'results__announced_on': 'max'  # latest funding date
        }).reset_index()
        
        companies.columns = ['uuid', 'company', 'website_url', 'raised_usd', 'latest_funding']
        
        # Add default values
        companies['employees'] = 1  # Default to 1 to avoid division by zero
        companies['country'] = 'Unknown'  # We don't have country data in this dataset
        
        # Fetch extra data if requested
        if st.button("Fetch Extra Data"):
            st.info("Fetching additional data... This may take a while.")
            extra_data = {}
            for _, row in companies.iterrows():
                company_data = fetch_company_data(row['company'], row['website_url'])
                extra_data[row['company']] = company_data
            
            # Update dataframe with extra data
            companies['languages'] = companies['company'].map(lambda x: extra_data.get(x, {}).get('languages', 0))
            companies['rating'] = companies['company'].map(lambda x: extra_data.get(x, {}).get('rating', 'N/A'))
        
        # Calculate pillar scores
        companies['efficiency'] = companies['raised_usd'] / companies['employees']
        
        # Handle any NaN values
        companies = companies.replace([np.inf, -np.inf], np.nan)
        companies = companies.fillna({
            'efficiency': 0,
            'languages': 0,
            'rating': 'N/A'
        })

        # Scale scores to 0-100
        scaler = MinMaxScaler(feature_range=(0, 100))
        companies['access_score'] = scaler.fit_transform(companies[['languages']])
        companies['efficiency_score'] = scaler.fit_transform(companies[['efficiency']])
        companies['service_quality_score'] = companies['rating'].apply(
            lambda x: 0 if x == 'N/A' else float(x)
        )
        
        # Calculate overall score
        companies['overall_score'] = companies[['access_score', 'efficiency_score', 'service_quality_score']].mean(axis=1)
        companies['moonfire_rank'] = companies['overall_score'].rank(ascending=False)
        
        # Create scatter plot
        fig = px.scatter(
            companies,
            x='languages',
            y='efficiency',
            size='service_quality_score',
            color='country',
            hover_data=['company', 'access_score', 'efficiency_score', 'service_quality_score'],
            title="Golden-Triangle Scorecard Visualization"
        )
        st.plotly_chart(fig)

        # Create Ag-Grid table
        gb = GridOptionsBuilder.from_dataframe(companies)
        gb.configure_pagination()
        gb.configure_default_column(editable=False, groupable=True)
        gb.configure_column("company", header_name="Company")
        gb.configure_column("country", header_name="Country")
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
            2. EFFICIENCY: Total capital raised USD ÷ employee count (scaled 0-100)
            3. SERVICE QUALITY: Average rating from G2 or Capterra (raw score)
            
            Scores are normalized to a 0-100 scale and averaged to determine the overall score.
            """)

        with st.expander("Caveats/Next Steps"):
            st.markdown("""
            - Data fetching is rate-limited and may fail for some companies
            - Ratings are scraped from G2/Capterra and may not be up-to-date
            - Language detection is based on website metadata and may be incomplete
            - Future improvements: Add more data sources, refine scoring, add more metrics
            """)

        with st.expander("About You"):
            st.markdown("""
            Placeholder text for about section.
            Add your information here.
            """)

    except Exception as e:
        st.error(f"Error processing data: {str(e)}")

if __name__ == "__main__":
    main()
