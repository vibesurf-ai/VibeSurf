"""
Comprehensive finance tools using Yahoo Finance API.
Provides access to stock market data, company financials, and trading information.
"""
import pdb
from enum import Enum
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
from datetime import datetime

from vibe_surf.logger import get_logger

logger = get_logger(__name__)


class FinanceMethod(Enum):
    """Available Yahoo Finance data methods"""
    # Basic Information
    GET_INFO = "get_info"  # Company basic information
    GET_FAST_INFO = "get_fast_info"  # Quick stats like current price, volume
    
    # Market Data & History
    GET_HISTORY = "get_history"  # Historical price and volume data
    GET_ACTIONS = "get_actions"  # Dividends and stock splits
    GET_DIVIDENDS = "get_dividends"  # Dividend history
    GET_SPLITS = "get_splits"  # Stock split history
    GET_CAPITAL_GAINS = "get_capital_gains"  # Capital gains distributions
    
    # Financial Statements
    GET_FINANCIALS = "get_financials"  # Income statement (annual)
    GET_QUARTERLY_FINANCIALS = "get_quarterly_financials"  # Income statement (quarterly)
    GET_BALANCE_SHEET = "get_balance_sheet"  # Balance sheet (annual)
    GET_QUARTERLY_BALANCE_SHEET = "get_quarterly_balance_sheet"  # Balance sheet (quarterly)
    GET_CASHFLOW = "get_cashflow"  # Cash flow statement (annual)
    GET_QUARTERLY_CASHFLOW = "get_quarterly_cashflow"  # Cash flow statement (quarterly)
    
    # Earnings & Analysis
    GET_EARNINGS = "get_earnings"  # Historical earnings data
    GET_QUARTERLY_EARNINGS = "get_quarterly_earnings"  # Quarterly earnings
    GET_EARNINGS_DATES = "get_earnings_dates"  # Upcoming earnings dates
    GET_CALENDAR = "get_calendar"  # Earnings calendar
    
    # Recommendations & Analysis
    GET_RECOMMENDATIONS = "get_recommendations"  # Analyst recommendations
    GET_RECOMMENDATIONS_SUMMARY = "get_recommendations_summary"  # Summary of recommendations
    GET_UPGRADES_DOWNGRADES = "get_upgrades_downgrades"  # Rating changes
    GET_ANALYSIS = "get_analysis"  # Analyst analysis
    
    # Ownership & Holdings
    GET_MAJOR_HOLDERS = "get_major_holders"  # Major shareholders
    GET_INSTITUTIONAL_HOLDERS = "get_institutional_holders"  # Institutional holdings
    GET_MUTUALFUND_HOLDERS = "get_mutualfund_holders"  # Mutual fund holdings
    GET_INSIDER_PURCHASES = "get_insider_purchases"  # Insider purchases
    GET_INSIDER_TRANSACTIONS = "get_insider_transactions"  # Insider transactions
    GET_INSIDER_ROSTER_HOLDERS = "get_insider_roster_holders"  # Insider roster
    
    # Additional Data
    GET_NEWS = "get_news"  # Latest news
    GET_SUSTAINABILITY = "get_sustainability"  # ESG scores
    GET_SEC_FILINGS = "get_sec_filings"  # SEC filings
    GET_SHARES = "get_shares"  # Share count data
    
    # Options (if applicable)
    GET_OPTIONS = "get_options"  # Option chain data


class FinanceDataRetriever:
    """Main class for retrieving and formatting Yahoo Finance data"""
    
    def __init__(self, symbol: str):
        """Initialize with stock symbol"""
        self.symbol = symbol.upper()
        self.ticker = yf.Ticker(self.symbol)
        
    def get_finance_data(self, methods: List[str], **kwargs) -> Dict[str, Any]:
        """
        Retrieve finance data using specified methods
        
        Args:
            methods: List of method names (FinanceMethod enum values)
            **kwargs: Additional parameters (e.g., period, start_date, end_date, num_news)
        
        Returns:
            Dictionary with method names as keys and data as values
        """
        results = {}
        
        for method in methods:
            try:
                if hasattr(self, f"_{method}"):
                    method_func = getattr(self, f"_{method}")
                    results[method] = method_func(**kwargs)
                else:
                    results[method] = f"Error: Method {method} not implemented"
                    logger.warning(f"Method {method} not implemented for {self.symbol}")
            except Exception as e:
                error_msg = f"Error retrieving {method}: {str(e)}"
                results[method] = error_msg
                logger.error(f"Error retrieving {method} for {self.symbol}: {e}")
        
        return results
    
    # Basic Information Methods
    def _get_info(self, **kwargs) -> Dict:
        """Get basic company information"""
        return self.ticker.info
    
    def _get_fast_info(self, **kwargs) -> Dict:
        """Get quick statistics"""
        try:
            fast_info = self.ticker.fast_info
            return dict(fast_info) if hasattr(fast_info, '__dict__') else fast_info
        except:
            return self.ticker.get_fast_info()
    
    # Market Data & History Methods
    def _get_history(self, **kwargs) -> pd.DataFrame:
        """Get historical price and volume data"""
        period = kwargs.get('period', '1y')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        interval = kwargs.get('interval', '1d')
        
        if start_date and end_date:
            return self.ticker.history(start=start_date, end=end_date, interval=interval)
        else:
            return self.ticker.history(period=period, interval=interval)
    
    def _get_actions(self, **kwargs) -> pd.DataFrame:
        """Get dividend and stock split history"""
        return self.ticker.actions
    
    def _get_dividends(self, **kwargs) -> pd.Series:
        """Get dividend history"""
        return self.ticker.dividends
    
    def _get_splits(self, **kwargs) -> pd.Series:
        """Get stock split history"""
        return self.ticker.splits
    
    def _get_capital_gains(self, **kwargs) -> pd.Series:
        """Get capital gains distributions"""
        return self.ticker.capital_gains
    
    # Financial Statements Methods
    def _get_financials(self, **kwargs) -> pd.DataFrame:
        """Get annual income statement"""
        return self.ticker.financials
    
    def _get_quarterly_financials(self, **kwargs) -> pd.DataFrame:
        """Get quarterly income statement"""
        return self.ticker.quarterly_financials
    
    def _get_balance_sheet(self, **kwargs) -> pd.DataFrame:
        """Get annual balance sheet"""
        return self.ticker.balance_sheet
    
    def _get_quarterly_balance_sheet(self, **kwargs) -> pd.DataFrame:
        """Get quarterly balance sheet"""
        return self.ticker.quarterly_balance_sheet
    
    def _get_cashflow(self, **kwargs) -> pd.DataFrame:
        """Get annual cash flow statement"""
        return self.ticker.cashflow
    
    def _get_quarterly_cashflow(self, **kwargs) -> pd.DataFrame:
        """Get quarterly cash flow statement"""
        return self.ticker.quarterly_cashflow
    
    # Earnings & Analysis Methods
    def _get_earnings(self, **kwargs) -> pd.DataFrame:
        """Get historical earnings data"""
        return self.ticker.earnings
    
    def _get_quarterly_earnings(self, **kwargs) -> pd.DataFrame:
        """Get quarterly earnings data"""
        return self.ticker.quarterly_earnings
    
    def _get_earnings_dates(self, **kwargs) -> pd.DataFrame:
        """Get earnings dates and estimates"""
        return self.ticker.earnings_dates
    
    def _get_calendar(self, **kwargs) -> Dict:
        """Get earnings calendar"""
        return self.ticker.calendar
    
    # Recommendations & Analysis Methods
    def _get_recommendations(self, **kwargs) -> pd.DataFrame:
        """Get analyst recommendations history"""
        return self.ticker.recommendations
    
    def _get_recommendations_summary(self, **kwargs) -> pd.DataFrame:
        """Get summary of analyst recommendations"""
        return self.ticker.recommendations_summary
    
    def _get_upgrades_downgrades(self, **kwargs) -> pd.DataFrame:
        """Get analyst upgrades and downgrades"""
        return self.ticker.upgrades_downgrades
    
    def _get_analysis(self, **kwargs) -> pd.DataFrame:
        """Get analyst analysis"""
        return getattr(self.ticker, 'analysis', pd.DataFrame())
    
    # Ownership & Holdings Methods
    def _get_major_holders(self, **kwargs) -> pd.DataFrame:
        """Get major shareholders"""
        return self.ticker.major_holders
    
    def _get_institutional_holders(self, **kwargs) -> pd.DataFrame:
        """Get institutional holdings"""
        return self.ticker.institutional_holders
    
    def _get_mutualfund_holders(self, **kwargs) -> pd.DataFrame:
        """Get mutual fund holdings"""
        return self.ticker.mutualfund_holders
    
    def _get_insider_purchases(self, **kwargs) -> pd.DataFrame:
        """Get insider purchases"""
        return getattr(self.ticker, 'insider_purchases', pd.DataFrame())
    
    def _get_insider_transactions(self, **kwargs) -> pd.DataFrame:
        """Get insider transactions"""
        return getattr(self.ticker, 'insider_transactions', pd.DataFrame())
    
    def _get_insider_roster_holders(self, **kwargs) -> pd.DataFrame:
        """Get insider roster"""
        return getattr(self.ticker, 'insider_roster_holders', pd.DataFrame())
    
    # Additional Data Methods
    def _get_news(self, **kwargs) -> List[Dict]:
        """Get latest news"""
        num_news = kwargs.get('num_news', 5)
        news = self.ticker.news
        return news[:num_news] if news else []
    
    def _get_sustainability(self, **kwargs) -> pd.DataFrame:
        """Get ESG sustainability data"""
        return getattr(self.ticker, 'sustainability', pd.DataFrame())
    
    def _get_sec_filings(self, **kwargs) -> pd.DataFrame:
        """Get SEC filings"""
        return getattr(self.ticker, 'sec_filings', pd.DataFrame())
    
    def _get_shares(self, **kwargs) -> pd.DataFrame:
        """Get share count data"""
        return getattr(self.ticker, 'shares', pd.DataFrame())
    
    def _get_options(self, **kwargs) -> Dict:
        """Get options data"""
        try:
            option_dates = self.ticker.options
            if option_dates:
                # Get the first available expiration date
                first_expiry = option_dates[0]
                opt_chain = self.ticker.option_chain(first_expiry)
                return {
                    'expiration_dates': list(option_dates),
                    'calls': opt_chain.calls,
                    'puts': opt_chain.puts,
                    'selected_expiry': first_expiry
                }
            return {'expiration_dates': [], 'calls': pd.DataFrame(), 'puts': pd.DataFrame()}
        except:
            return {'error': 'Options data not available for this ticker'}


class FinanceMarkdownFormatter:
    """Formats finance data into markdown"""
    
    @staticmethod
    def format_finance_data(symbol: str, results: Dict[str, Any], methods: List[str]) -> str:
        """Format all finance data as markdown"""
        markdown = f"# 💹 Financial Data for {symbol.upper()}\n\n"
        
        for method in methods:
            data = results.get(method)
            
            if isinstance(data, str) and data.startswith('Error'):
                markdown += f"## ❌ {method.replace('_', ' ').title()}\n{data}\n\n"
                continue
                
            markdown += f"## 📊 {method.replace('_', ' ').title()}\n\n"
            
            # Route to appropriate formatter
            formatter_method = f"_format_{method}"
            if hasattr(FinanceMarkdownFormatter, formatter_method):
                formatter = getattr(FinanceMarkdownFormatter, formatter_method)
                markdown += formatter(data)
            else:
                # Generic formatter for unhandled methods
                markdown += FinanceMarkdownFormatter._format_generic(data)
                
            markdown += "\n\n"
        
        return markdown.strip()
    
    @staticmethod
    def _format_generic(data: Any) -> str:
        """Generic formatter for any data type"""
        if data is None or (hasattr(data, 'empty') and data.empty):
            return "No data available.\n"
        
        if isinstance(data, pd.DataFrame):
            if len(data) == 0:
                return "No data available.\n"
            return f"```\n{data.to_string()}\n```\n"
        elif isinstance(data, pd.Series):
            if len(data) == 0:
                return "No data available.\n"
            return f"```\n{data.to_string()}\n```\n"
        elif isinstance(data, (list, dict)):
            import json
            return f"```json\n{json.dumps(data, indent=2, default=str)}\n```\n"
        else:
            return f"```\n{str(data)}\n```\n"
    
    @staticmethod
    def _format_get_info(info: Dict) -> str:
        """Format company info as markdown"""
        if not info:
            return "No company information available.\n"
            
        markdown = ""
        
        # Basic company info
        if 'longName' in info:
            markdown += f"**Company Name:** {info['longName']}\n"
        if 'sector' in info:
            markdown += f"**Sector:** {info['sector']}\n"
        if 'industry' in info:
            markdown += f"**Industry:** {info['industry']}\n"
        if 'website' in info:
            markdown += f"**Website:** {info['website']}\n"
        if 'country' in info:
            markdown += f"**Country:** {info['country']}\n"
        
        markdown += "\n### 💰 Financial Metrics\n"
        
        # Financial metrics
        if 'marketCap' in info and info['marketCap']:
            markdown += f"**Market Cap:** ${info['marketCap']:,.0f}\n"
        if 'enterpriseValue' in info and info['enterpriseValue']:
            markdown += f"**Enterprise Value:** ${info['enterpriseValue']:,.0f}\n"
        if 'totalRevenue' in info and info['totalRevenue']:
            markdown += f"**Total Revenue:** ${info['totalRevenue']:,.0f}\n"
        if 'grossMargins' in info and info['grossMargins']:
            markdown += f"**Gross Margin:** {info['grossMargins']:.2%}\n"
        if 'profitMargins' in info and info['profitMargins']:
            markdown += f"**Profit Margin:** {info['profitMargins']:.2%}\n"
        
        markdown += "\n### 📈 Stock Price Info\n"
        
        # Stock price info
        if 'currentPrice' in info and info['currentPrice']:
            markdown += f"**Current Price:** ${info['currentPrice']:.2f}\n"
        if 'previousClose' in info and info['previousClose']:
            markdown += f"**Previous Close:** ${info['previousClose']:.2f}\n"
        if 'fiftyTwoWeekHigh' in info and info['fiftyTwoWeekHigh']:
            markdown += f"**52 Week High:** ${info['fiftyTwoWeekHigh']:.2f}\n"
        if 'fiftyTwoWeekLow' in info and info['fiftyTwoWeekLow']:
            markdown += f"**52 Week Low:** ${info['fiftyTwoWeekLow']:.2f}\n"
        if 'dividendYield' in info and info['dividendYield']:
            markdown += f"**Dividend Yield:** {info['dividendYield']:.2%}\n"
        
        # Business summary
        if 'longBusinessSummary' in info:
            summary = info['longBusinessSummary'][:500]
            if len(info['longBusinessSummary']) > 500:
                summary += "..."
            markdown += f"\n### 📋 Business Summary\n{summary}\n"
        
        return markdown
    
    @staticmethod
    def _format_get_fast_info(fast_info) -> str:
        """Format fast info as markdown"""
        if not fast_info:
            return "No fast info available.\n"
            
        markdown = ""
        
        # Convert to dict if needed
        if hasattr(fast_info, '__dict__'):
            data = fast_info.__dict__
        elif isinstance(fast_info, dict):
            data = fast_info
        else:
            return f"Fast info data: {str(fast_info)}\n"
        
        # Format key metrics
        for key, value in data.items():
            if value is not None:
                key_formatted = key.replace('_', ' ').title()
                if isinstance(value, (int, float)):
                    if 'price' in key.lower() or 'value' in key.lower():
                        markdown += f"**{key_formatted}:** ${value:,.2f}\n"
                    elif 'volume' in key.lower():
                        markdown += f"**{key_formatted}:** {value:,}\n"
                    else:
                        markdown += f"**{key_formatted}:** {value}\n"
                else:
                    markdown += f"**{key_formatted}:** {value}\n"
        
        return markdown
    
    @staticmethod
    def _format_get_history(history: pd.DataFrame) -> str:
        """Format historical data as markdown"""
        if history.empty:
            return "No historical data available.\n"
        
        markdown = f"**Period:** {history.index.min().strftime('%Y-%m-%d')} to {history.index.max().strftime('%Y-%m-%d')}\n"
        markdown += f"**Total Records:** {len(history)}\n\n"
        
        # Determine how much data to show based on total records
        total_records = len(history)
        if total_records <= 30:
            # Show all data if 30 records or less
            display_data = history
            markdown += f"### 📈 Historical Data (All {total_records} Records)\n\n"
        else:
            # Show recent 30 records for larger datasets
            display_data = history.tail(30)
            markdown += f"### 📈 Recent Data (Last 30 Records)\n\n"
        
        markdown += "| Date | Open | High | Low | Close | Volume |\n"
        markdown += "|------|------|------|-----|-------|--------|\n"
        
        for date, row in display_data.iterrows():
            markdown += f"| {date.strftime('%Y-%m-%d')} | ${row['Open']:.2f} | ${row['High']:.2f} | ${row['Low']:.2f} | ${row['Close']:.2f} | {row['Volume']:,} |\n"
        
        # Summary statistics
        markdown += "\n### 📊 Summary Statistics\n"
        markdown += f"**Highest Price:** ${history['High'].max():.2f}\n"
        markdown += f"**Lowest Price:** ${history['Low'].min():.2f}\n"
        markdown += f"**Average Volume:** {history['Volume'].mean():,.0f}\n"
        markdown += f"**Total Volume:** {history['Volume'].sum():,}\n"
        
        return markdown
    
    @staticmethod
    def _format_get_news(news: List[Dict]) -> str:
        """Format news data as markdown"""
        if not news:
            return "No news available.\n"
            
        markdown = f"**Total News Articles:** {len(news)}\n\n"
        for i, article in enumerate(news, 1):
            if isinstance(article, dict):
                # Handle new yfinance news structure with nested 'content'
                content = article.get('content', article)  # Fallback to article itself for backwards compatibility
                
                # Extract title
                title = (content.get('title') or
                        content.get('headline') or
                        content.get('summary') or
                        article.get('title') or  # Fallback to old format
                        'No title available')
                
                # Extract content type if available
                content_type = content.get('contentType', '')
                type_emoji = "🎥" if content_type == "VIDEO" else "📰"
                
                # Extract link/URL - try new nested structure first
                link = ''
                if 'canonicalUrl' in content and isinstance(content['canonicalUrl'], dict):
                    link = content['canonicalUrl'].get('url', '')
                elif 'clickThroughUrl' in content and isinstance(content['clickThroughUrl'], dict):
                    link = content['clickThroughUrl'].get('url', '')
                else:
                    # Fallback to old format
                    link = (content.get('link') or
                           content.get('url') or
                           content.get('guid') or
                           article.get('link') or '')
                
                # Extract publisher - try new nested structure first
                publisher = 'Unknown'
                if 'provider' in content and isinstance(content['provider'], dict):
                    publisher = content['provider'].get('displayName', 'Unknown')
                else:
                    # Fallback to old format
                    publisher = (content.get('publisher') or
                               content.get('source') or
                               content.get('author') or
                               article.get('publisher') or
                               'Unknown')
                
                # Extract publication time
                publish_time = (content.get('pubDate') or
                              content.get('providerPublishTime') or
                              content.get('timestamp') or
                              content.get('published') or
                              article.get('providerPublishTime') or '')
                
                # Format the article
                markdown += f"### {type_emoji} {i}. {title}\n"
                if content_type:
                    markdown += f"**Type:** {content_type}\n"
                markdown += f"**Publisher:** {publisher}\n"
                
                if publish_time:
                    try:
                        # Handle different timestamp formats
                        if isinstance(publish_time, (int, float)):
                            dt = datetime.fromtimestamp(publish_time)
                            markdown += f"**Published:** {dt.strftime('%Y-%m-%d %H:%M')}\n"
                        elif isinstance(publish_time, str):
                            # Try to parse ISO format first (new format)
                            try:
                                if publish_time.endswith('Z'):
                                    dt = datetime.fromisoformat(publish_time.replace('Z', '+00:00'))
                                    markdown += f"**Published:** {dt.strftime('%Y-%m-%d %H:%M UTC')}\n"
                                else:
                                    # Try to parse as Unix timestamp
                                    publish_time_int = int(float(publish_time))
                                    dt = datetime.fromtimestamp(publish_time_int)
                                    markdown += f"**Published:** {dt.strftime('%Y-%m-%d %H:%M')}\n"
                            except:
                                markdown += f"**Published:** {publish_time}\n"
                    except Exception as e:
                        # If timestamp parsing fails, show raw value
                        markdown += f"**Published:** {publish_time}\n"
                
                if link:
                    markdown += f"**Link:** {link}\n"
                
                # Add summary or description if available
                summary = (content.get('summary') or
                          content.get('description') or
                          content.get('snippet') or
                          article.get('summary') or '')
                if summary and summary != title:
                    # Clean HTML tags from description if present
                    import re
                    clean_summary = re.sub(r'<[^>]+>', '', summary)
                    clean_summary = re.sub(r'\s+', ' ', clean_summary).strip()
                    
                    # Limit summary length
                    if len(clean_summary) > 300:
                        clean_summary = clean_summary[:300] + "..."
                    markdown += f"**Summary:** {clean_summary}\n"
                
                # Add metadata if available
                if 'metadata' in content and isinstance(content['metadata'], dict):
                    if content['metadata'].get('editorsPick'):
                        markdown += f"**Editor's Pick:** ✅\n"
                
                markdown += "\n"
        
        return markdown
    
    @staticmethod
    def _format_get_dividends(dividends: pd.Series) -> str:
        """Format dividend data as markdown"""
        if dividends.empty:
            return "No dividend data available.\n"

        markdown = f"**Total Dividends Recorded:** {len(dividends)}\n"
        markdown += f"**Date Range:** {dividends.index.min().strftime('%Y-%m-%d')} to {dividends.index.max().strftime('%Y-%m-%d')}\n\n"

        # Recent dividends (last 10)
        recent_dividends = dividends.tail(10)
        markdown += "### 💰 Recent Dividends\n\n"
        markdown += "| Date | Dividend Amount |\n"
        markdown += "|------|----------------|\n"
        
        for date, amount in recent_dividends.items():
            markdown += f"| {date.strftime('%Y-%m-%d')} | ${amount:.4f} |\n"
        
        # Summary
        markdown += f"\n**Total Dividends Paid:** ${dividends.sum():.4f}\n"
        markdown += f"**Average Dividend:** ${dividends.mean():.4f}\n"
        if len(dividends) > 1:
            yearly_frequency = len(dividends) / ((dividends.index.max() - dividends.index.min()).days / 365.25)
            markdown += f"**Estimated Annual Frequency:** {yearly_frequency:.1f} times per year\n"
        
        return markdown
    
    @staticmethod
    def _format_get_recommendations(recommendations: pd.DataFrame) -> str:
        """Format recommendations as markdown"""
        if recommendations.empty:
            return "No recommendations available.\n"
            
        markdown = f"**Total Recommendations:** {len(recommendations)}\n\n"
        
        # Recent recommendations (last 15)
        recent_recs = recommendations.tail(15)
        markdown += "### 📊 Recent Analyst Recommendations\n\n"
        markdown += "| Date | Firm | To Grade | From Grade | Action |\n"
        markdown += "|------|------|----------|------------|--------|\n"
        
        for _, rec in recent_recs.iterrows():
            date = rec.get('Date', 'N/A')
            firm = rec.get('Firm', 'N/A')
            to_grade = rec.get('To Grade', 'N/A')
            from_grade = rec.get('From Grade', 'N/A')
            action = rec.get('Action', 'N/A')
            
            markdown += f"| {date} | {firm} | {to_grade} | {from_grade} | {action} |\n"
        
        return markdown
    
    @staticmethod
    def _format_get_earnings(earnings: pd.DataFrame) -> str:
        """Format earnings as markdown"""
        if earnings.empty:
            return "No earnings data available.\n"
            
        markdown = "### 💼 Annual Earnings History\n\n"
        markdown += "| Year | Revenue | Earnings |\n"
        markdown += "|------|---------|----------|\n"
        
        for year, row in earnings.iterrows():
            revenue = row.get('Revenue', 'N/A')
            earnings_val = row.get('Earnings', 'N/A')
            
            # Format numbers if they're numeric
            if isinstance(revenue, (int, float)):
                revenue = f"${revenue:,.0f}"
            if isinstance(earnings_val, (int, float)):
                earnings_val = f"${earnings_val:,.0f}"
            
            markdown += f"| {year} | {revenue} | {earnings_val} |\n"
        
        return markdown