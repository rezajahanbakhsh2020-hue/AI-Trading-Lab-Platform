export interface AcademyCategory {
  id: string;
  title: string;
  icon: string;
  shortDescription: string;
  articles: AcademyArticle[];
}

export interface AcademyArticle {
  id: string;
  title: string;
  readTime: string;
  level: "Beginner" | "Intermediate" | "Advanced";
  summary: string;
  sections: {
    heading: string;
    body: string;
    bulletPoints?: string[];
  }[];
}

export interface GlossaryItem {
  term: string;
  category: string;
  definition: string;
  formulaOrExample?: string;
}

export const ACADEMY_CATEGORIES: AcademyCategory[] = [
  {
    id: "basics",
    title: "1. Trading Basics",
    icon: "book",
    shortDescription: "Essential concepts, market structures, and financial instruments.",
    articles: [
      {
        id: "intro-financial-markets",
        title: "Introduction to Financial Markets",
        readTime: "4 min read",
        level: "Beginner",
        summary: "Understand how buyers and sellers interact in spot, futures, and derivative markets.",
        sections: [
          {
            heading: "What are Financial Markets?",
            body: "Financial markets serve as central venues where participants exchange asset classes such as commodities (e.g. Gold XAU/USD), currencies (Forex), equities, and digital assets. Prices fluctuate based on supply, demand, economic indicators, and liquidity.",
            bulletPoints: [
              "Spot Market: Instant settlement of trades at market price.",
              "Derivatives & Futures: Contracts based on future asset prices.",
              "Liquidity: Ease of buying or selling without impacting asset price.",
            ],
          },
          {
            heading: "Bid, Ask, and Spread",
            body: "The Bid is the highest price a buyer is willing to pay. The Ask (Offer) is the lowest price a seller is willing to accept. The difference between Bid and Ask is the Spread, representing transaction cost.",
          },
        ],
      },
    ],
  },
  {
    id: "how-trading-works",
    title: "2. How Trading Works",
    icon: "refresh",
    shortDescription: "Orders, execution mechanics, slippage, and broker routing.",
    articles: [
      {
        id: "order-types-and-execution",
        title: "Order Types & Market Execution",
        readTime: "5 min read",
        level: "Beginner",
        summary: "Master Market, Limit, Stop, and Stop-Limit order execution mechanics.",
        sections: [
          {
            heading: "Order Types Explained",
            body: "Selecting the correct order type ensures execution control during volatile trading conditions.",
            bulletPoints: [
              "Market Order: Executes immediately at best available current price.",
              "Limit Order: Executes only at specified target price or better.",
              "Stop Order: Converts into market order once trigger price is hit.",
              "Stop-Limit Order: Converts into limit order when trigger price is reached.",
            ],
          },
        ],
      },
    ],
  },
  {
    id: "technical-analysis",
    title: "3. Technical Analysis",
    icon: "chart",
    shortDescription: "Price action, candlesticks, support/resistance, and indicators.",
    articles: [
      {
        id: "candlestick-patterns",
        title: "Candlestick Anatomy & Price Action",
        readTime: "6 min read",
        level: "Beginner",
        summary: "Read Open, High, Low, and Close (OHLC) price movement on Japanese candlesticks.",
        sections: [
          {
            heading: "OHLC Structure",
            body: "Each candlestick visualizes price movement over a selected timeframe (M1, M5, H1, D1). The body represents the range between Open and Close, while the wicks (shadows) mark the High and Low.",
          },
        ],
      },
    ],
  },
  {
    id: "risk-management",
    title: "4. Risk Management",
    icon: "shield",
    shortDescription: "Position sizing, stop-loss strategy, risk-to-reward ratio (R:R), and capital preservation.",
    articles: [
      {
        id: "position-sizing-rr",
        title: "Position Sizing & Risk-to-Reward Ratio",
        readTime: "5 min read",
        level: "Intermediate",
        summary: "Protect trading capital using strict risk percent limits per position.",
        sections: [
          {
            heading: "The 1% Risk Rule",
            body: "Professional traders rarely risk more than 1% to 2% of total equity on any individual trade setup. This ensures surviving extended drawdown series.",
            bulletPoints: [
              "Risk Amount = Account Equity x Risk Percentage",
              "Position Size = Risk Amount / (Entry Price - Stop Loss Price)",
              "Minimum R:R Target: 1:2 or higher recommended.",
            ],
          },
        ],
      },
    ],
  },
  {
    id: "strategy-concepts",
    title: "5. Strategy Concepts",
    icon: "cpu",
    shortDescription: "Algorithmic rules, trend following, mean reversion, and breakout systems.",
    articles: [
      {
        id: "rule-based-strategies",
        title: "Rule-Based Systematic Trading",
        readTime: "6 min read",
        level: "Intermediate",
        summary: "Eliminate emotional bias by defining objective entry, exit, and filtering rules.",
        sections: [
          {
            heading: "Quantitative Rules",
            body: "A trading strategy consists of objective quantitative conditions evaluated against incoming market data. Rules specify entry criteria, invalidation (stop loss), profit targets (TP1, TP2, TP3), and stability criteria.",
          },
        ],
      },
    ],
  },
  {
    id: "backtesting",
    title: "6. Backtesting",
    icon: "history",
    shortDescription: "Historical strategy evaluation, curve fitting risks, and metrics analysis.",
    articles: [
      {
        id: "backtesting-fundamentals",
        title: "Historical Backtest Evaluation",
        readTime: "7 min read",
        level: "Intermediate",
        summary: "Simulate strategy rules over multi-year historical price data.",
        sections: [
          {
            heading: "Key Backtest Metrics",
            body: "Evaluating backtest quality requires reviewing win rate, profit factor, max drawdown, and total executed trades.",
            bulletPoints: [
              "Profit Factor: Gross Profits / Gross Losses (> 1.5 target).",
              "Max Drawdown: Largest peak-to-trough decline in equity.",
              "Overfitting Risk: Fitting rules to historical noise rather than real edge.",
            ],
          },
        ],
      },
    ],
  },
  {
    id: "walk-forward",
    title: "7. Walk-Forward Validation",
    icon: "check-circle",
    shortDescription: "Out-of-sample testing, parameter stability, and robustness verification.",
    articles: [
      {
        id: "walk-forward-validation",
        title: "Out-of-Sample Walk-Forward Analysis",
        readTime: "8 min read",
        level: "Advanced",
        summary: "Validate that strategy performance persists on unseen out-of-sample data.",
        sections: [
          {
            heading: "In-Sample vs Out-of-Sample",
            body: "Optimization is performed on In-Sample (IS) historical segments, then strictly validated on sequential Out-of-Sample (OOS) data blocks to confirm strategy robustness.",
          },
        ],
      },
    ],
  },
  {
    id: "signals",
    title: "8. Signals",
    icon: "zap",
    shortDescription: "Signal lifecycle, timestamps, validation status, and automated alerts.",
    articles: [
      {
        id: "signal-anatomy",
        title: "Understanding Signal Lifecycle",
        readTime: "4 min read",
        level: "Intermediate",
        summary: "How Project 1 generates and emits validated trading signals.",
        sections: [
          {
            heading: "Signal Actions & Context",
            body: "Signals emit actions BUY, SELL, HOLD, or NO SIGNAL alongside exact entry price, Stop Loss, Take Profit targets, stability score, and timestamp.",
          },
        ],
      },
    ],
  },
  {
    id: "trading-psychology",
    title: "9. Trading Psychology",
    icon: "heart",
    shortDescription: "Discipline, managing drawdown, FOMO, and systematic execution mindset.",
    articles: [
      {
        id: "psychology-and-drawdown",
        title: "Navigating Drawdown & Emotional Discipline",
        readTime: "5 min read",
        level: "Beginner",
        summary: "Maintain adherence to quantitative system rules during losing streaks.",
        sections: [
          {
            heading: "The Mindset of Systematic Trading",
            body: "Trusting quantitative validation metrics (stability score, backtest walk-forward results) prevents panic-closing positions or altering strategy rules during normal statistical drawdowns.",
          },
        ],
      },
    ],
  },
  {
    id: "glossary",
    title: "10. Glossary",
    icon: "list",
    shortDescription: "Comprehensive financial and quantitative trading terminology index.",
    articles: [
      {
        id: "trading-glossary-guide",
        title: "Trading & Quantitative Terminology Reference",
        readTime: "10 min read",
        level: "Beginner",
        summary: "Definitions for essential trading, risk, and algorithmic terms.",
        sections: [
          {
            heading: "Essential Index",
            body: "Use the interactive search and filter bar in the Glossary section below to find definitions.",
          },
        ],
      },
    ],
  },
];

export const GLOSSARY_ITEMS: GlossaryItem[] = [
  {
    term: "Drawdown (Max Drawdown)",
    category: "Risk",
    definition: "The peak-to-trough decline in account equity during a specific trading period, expressed as a percentage or dollar value.",
    formulaOrExample: "Max Drawdown % = ((Peak Equity - Trough Equity) / Peak Equity) * 100",
  },
  {
    term: "Profit Factor",
    category: "Performance",
    definition: "The ratio of gross profits to gross losses generated by a trading system over a test period.",
    formulaOrExample: "Profit Factor = Total Winning Trade Profits / Total Losing Trade Losses",
  },
  {
    term: "Sharpe Ratio",
    category: "Performance",
    definition: "A measure of risk-adjusted return comparing account return to risk-free rate divided by standard deviation of returns.",
    formulaOrExample: "Sharpe = (Mean System Return - Risk Free Rate) / Standard Deviation of Return",
  },
  {
    term: "Slippage",
    category: "Execution",
    definition: "The difference between expected order execution price and actual executed fill price due to market speed or volatility.",
    formulaOrExample: "Slippage = Fill Price - Requested Order Price",
  },
  {
    term: "Walk-Forward Validation",
    category: "Backtest",
    definition: "An algorithmic evaluation method where parameters are optimized on historical data (In-Sample) and tested on unseen future periods (Out-of-Sample).",
  },
  {
    term: "Stability Score",
    category: "Strategy",
    definition: "A quantitative metric rating how consistently a strategy performs across diverse market regimes and timeframes.",
  },
  {
    term: "Risk-to-Reward Ratio (R:R)",
    category: "Risk",
    definition: "The proportion of expected loss (distance to Stop Loss) compared to expected profit target (distance to Take Profit).",
    formulaOrExample: "R:R = (Take Profit Price - Entry Price) / (Entry Price - Stop Loss Price)",
  },
  {
    term: "XAU/USD",
    category: "Markets",
    definition: "The ticker symbol for Spot Gold quoted against the United States Dollar.",
  },
  {
    term: "Stop Loss (SL)",
    category: "Risk",
    definition: "A predetermined price level where an open trade is closed automatically to limit total loss.",
  },
  {
    term: "Take Profit (TP)",
    category: "Risk",
    definition: "A predetermined price level where an open trade is closed to lock in targeted profit.",
  },
  {
    term: "In-Sample (IS)",
    category: "Backtest",
    definition: "Historical price data used during strategy development and parameter tuning.",
  },
  {
    term: "Out-of-Sample (OOS)",
    category: "Backtest",
    definition: "Unseen historical price data used strictly for verifying that strategy performance is not overfitted.",
  },
];
