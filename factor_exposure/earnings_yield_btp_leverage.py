import numpy as np
import pandas as pd
import math
from datetime import datetime
from datetime import timedelta

import rqdatac

#rqdatac.init("ricequant", "Ricequant123", ('rqdatad-pro.ricequant.com', 16004))
rqdatac.init('ricequant', '8ricequant8',('q-tools.ricequant.com', 16010))


def recent_annual_report(date):
    latest_trading_date = str(
        rqdatac.get_previous_trading_date(datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)))

    previous_year = datetime.strptime(latest_trading_date, '%Y-%m-%d').year - 1

    # 取出最近一期财务报告类型，例如 '2016q3' 或  '2016q4'， 其中 '2016q3' 表示前三季度累计； '2016q4' 表示年报

    recent_report_type = rqdatac.get_fundamentals(rqdatac.query(rqdatac.fundamentals.income_statement.net_profit),
                                                  entry_date=latest_trading_date, interval='1y', report_quarter=True)['report_quarter']

    annual_report_type = recent_report_type.copy()  # 深拷贝

    # 若上市公司未发布今年的财报，且未发布去年的年报，则取前年的年报为最新年报

    if recent_report_type.T.iloc[0].values[0][:4] == str(previous_year):

        annual_report_type[annual_report_type != str(previous_year) + 'q4'] = str(previous_year - 1) + 'q4'

    # 若上市公司已发布今年的财报，则取去年的年报为最新年报

    else:
        annual_report_type[annual_report_type != str(previous_year) + 'q4'] = str(previous_year) + 'q4'

    # recent_report_type 和 annual_report_type 均为 dataframe 格式，输出时转为 Series 格式

    return recent_report_type.T[latest_trading_date], annual_report_type.T[latest_trading_date]


# 计算原生指标过去十二个月的滚动值（利润表、现金流量表滚动求和）
def ttm_sum(financial_indicator, date):

    recent_report_type, annual_report_type = recent_annual_report(date)
    latest_trading_date = str(rqdatac.get_previous_trading_date(datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)))
    previous_year = datetime.strptime(latest_trading_date, '%Y-%m-%d').year - 1

    # 获得最近一期报告为年报的股票列表

    annual_report_published_stocks = recent_report_type[recent_report_type == str(previous_year) + 'q4'].index.tolist()

    # 把 index 和 list 转为集合类型，再计算补集

    annual_report_not_published_stocks = list(set(recent_report_type.index) - set(annual_report_published_stocks))

    # TTM 计算对于未发布年报的企业仅考虑上市时间超过半年（183天）的股票(考虑到招股说明书披露相关财报)，以保证获得相关财务数据进行计算
    ttm_listed_date_threshold = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=183)).strftime("%Y-%m-%d")

    ttm_qualified_stocks = [i for i in annual_report_not_published_stocks if
                            rqdatac.instruments(i).listed_date < ttm_listed_date_threshold]

    # 计算最近一期财报为年报的股票的TTM
    annual_published_recent_annual_values = [
        rqdatac.get_financials(rqdatac.query(financial_indicator).filter(rqdatac.financials.stockcode.in_([stock])),
                               annual_report_type[stock], '1q').values[0] for stock in annual_report_published_stocks]

    annual_published_ttm_series = pd.Series(index=annual_report_published_stocks,
                                            data=annual_published_recent_annual_values)

    # 对于最近一期报告非年报的股票，获取其此前同期的报告
    previous_same_period = str(int(recent_report_type[0][:4]) - 1)

    previous_same_period_report_type = recent_report_type.loc[ttm_qualified_stocks].str.slice_replace(0, 4,previous_same_period)

    # 计算最近一期财报不是年报的股票的TTM

    # 最近一期季报/半年报取值

    recent_values = [
        rqdatac.get_financials(rqdatac.query(financial_indicator).filter(rqdatac.financials.stockcode.in_([stock])),
                               recent_report_type[stock], '1q').values[0] for stock in ttm_qualified_stocks]

    # 去年同期季报/半年报取值

    previous_same_period_values = [
        rqdatac.get_financials(rqdatac.query(financial_indicator).filter(rqdatac.financials.stockcode.in_([stock])),
                               previous_same_period_report_type[stock], '1q').values[0] for stock in ttm_qualified_stocks]

    # 最近一期年报报告取值

    recent_annual_values = [
        rqdatac.get_financials(rqdatac.query(financial_indicator).filter(rqdatac.financials.stockcode.in_([stock])),
                               annual_report_type[stock], '1q').values[0] for stock in ttm_qualified_stocks]

    ttm_values = np.array(recent_annual_values) + np.array(recent_values) - np.array(previous_same_period_values)

    annual_not_published_ttm_series = pd.Series(index=ttm_qualified_stocks, data=ttm_values)

    ttm_series = pd.concat([annual_published_ttm_series, annual_not_published_ttm_series], axis=0)

    return ttm_series


def ttm_mean(financial_indicator, date):

    recent_report_type, annual_report_type = recent_annual_report(date)

    # 取最近4期报表的平均值

    recent_values = [rqdatac.get_financials(rqdatac.query(financial_indicator
                                                          ).filter(rqdatac.financials.stockcode.in_([stock])
                                                                   ), recent_report_type[stock], '4q').values[0:4].mean() for stock in recent_report_type.index]

    recent_values_ttm = pd.Series(data=recent_values, index=recent_report_type.index)

    return recent_values_ttm


# 调取最近一期财报数据
def lf(financial_indicator, date):

    recent_report_type, annual_report_type = recent_annual_report(date)

    recent_annual_values = [rqdatac.get_financials(rqdatac.query(financial_indicator).filter(rqdatac.financials.stockcode.in_([stock])),
                                                   recent_report_type[stock], '1q').values[0] for stock in recent_report_type.index]

    lf_series = pd.Series(index=recent_report_type.index, data=recent_annual_values)

    return lf_series


# style: earnings yield
# ETOP:Trailing earning-to-price ratio
def earning_to_price_ratio(date):

    # 获取最近一个交易日
    latest_trading_date = str(rqdatac.get_previous_trading_date(datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)))

    # 行情数据部分取最近一个交易日数据

    market_cap_series = rqdatac.get_fundamentals(rqdatac.query(rqdatac.fundamentals.eod_derivative_indicator.market_cap),
                                                 entry_date=latest_trading_date, interval='1d')['market_cap']

    net_profit_ttm = ttm_sum(rqdatac.financials.income_statement.net_profit,date)

    ep_ratio = net_profit_ttm/market_cap_series[net_profit_ttm.index]

    return ep_ratio.T


# CETOP:Trailing cash earning to price ratio
def operating_cash_earnings_to_price_ratio(date):

    # 获取最近一个交易日
    latest_trading_date = str(
        rqdatac.get_previous_trading_date(datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)))

    cash_flow_from_operating_activities_ttm = ttm_sum(rqdatac.financials.cash_flow_statement.cash_flow_from_operating_activities,date)

    stock_list = cash_flow_from_operating_activities_ttm.index.tolist()

    total_shares = rqdatac.get_shares(stock_list,start_date=latest_trading_date, end_date=latest_trading_date, fields='total')

    share_price = rqdatac.get_price(stock_list,start_date=latest_trading_date,end_date=latest_trading_date,fields='close')

    operating_cash_per_share = cash_flow_from_operating_activities_ttm / total_shares

    cash_earning_to_price= operating_cash_per_share.T/share_price.T

    return cash_earning_to_price


# style: book-to-price  BTOP =股东权益合计/市值
def book_to_price_ratio_total(date):
    # 获取最近一个交易日
    latest_trading_date = str(
        rqdatac.get_previous_trading_date(datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)))

    # 行情数据部分取最近一个交易日数据

    market_cap_series = rqdatac.get_fundamentals(rqdatac.query(rqdatac.fundamentals.eod_derivative_indicator.market_cap),
                                                 entry_date=latest_trading_date, interval='1d')['market_cap']

    total_equity = lf(rqdatac.financials.balance_sheet.total_equity,date)

    bp_ratio = total_equity/market_cap_series[total_equity.index]

    return bp_ratio.T


# book-to-price = (股东权益合计-优先股)/市值
def book_to_price_ratio(date):
    # 获取最近一个交易日
    latest_trading_date = str(
        rqdatac.get_previous_trading_date(datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)))

    # 行情数据部分取最近一个交易日数据

    market_cap_series = rqdatac.get_fundamentals(rqdatac.query(rqdatac.fundamentals.eod_derivative_indicator.market_cap),
                                                 entry_date=latest_trading_date, interval='1d')['market_cap']

    total_equity = lf(rqdatac.financials.balance_sheet.total_equity,date)
    # 大多公司没有优先股，优先股空值比例高达98%，进行缺失值处理将空值替换为0
    prefer_stock = lf(rqdatac.financials.balance_sheet.equity_prefer_stock,date)
    prefer_stock = prefer_stock.fillna(value=0)

    bp_ratio = (total_equity-prefer_stock)/market_cap_series[total_equity.index]

    return bp_ratio.T


# style:leverage
# MLEV: Market leverage = (ME+PE+LD)/ME ME:最新市值 PE:最新优先股账面价值 LD:长期负债账面价值
# 根据Barra 因子解释：total debt=long term debt+current liabilities,在因子计算中使用非流动负债合计：non_current_liabilities作为long_term_debt
def market_leverage(date):
    # 获取最近一个交易日
    latest_trading_date = str(
        rqdatac.get_previous_trading_date(datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)))

    # 行情数据部分取最近一个交易日数据
    market_cap_series = \
    rqdatac.get_fundamentals(rqdatac.query(rqdatac.fundamentals.eod_derivative_indicator.market_cap),
                             entry_date=latest_trading_date, interval='1d')['market_cap']

    non_current_liabilities = lf(rqdatac.financials.balance_sheet.non_current_liabilities,date)
    non_current_liabilities = non_current_liabilities.fillna(value=0)
    # 大多公司没有优先股，优先股空值比例高达98%，进行缺失值处理将空值替换为0
    prefer_stock = lf(rqdatac.financials.balance_sheet.equity_prefer_stock, date)
    prefer_stock = prefer_stock.fillna(value=0)

    MLEV = (market_cap_series[non_current_liabilities.index]+non_current_liabilities+prefer_stock)/market_cap_series[non_current_liabilities.index]
    return MLEV.T


# DTOA:Debt_to_asset：total debt/total assets
def debt_to_asset(date):

    total_debt = lf(rqdatac.financials.balance_sheet.total_liabilities,date)

    total_asset = lf(rqdatac.financials.balance_sheet.total_assets,date)

    return pd.DataFrame(total_debt/total_asset)


# BLEV: book leverage = (BE+PE+LD)/BE BE:普通股权账面价值 PE：优先股账面价值 LD:长期负债账面价值
# 由于BE=total equity-equity_prefer_stock
def book_leverage(date):

    book_value_of_common_stock = lf(rqdatac.financials.balance_sheet.paid_in_capital,date)

    non_current_liabilities = lf(rqdatac.financials.balance_sheet.non_current_liabilities, date)
    non_current_liabilities = non_current_liabilities.fillna(value=0)

    # 大多公司没有优先股，优先股空值比例高达98%，进行缺失值处理将空值替换为0
    prefer_stock = lf(rqdatac.financials.balance_sheet.equity_prefer_stock, date)
    prefer_stock = prefer_stock.fillna(value=0)

    BLEV = (book_value_of_common_stock+prefer_stock+non_current_liabilities)/book_value_of_common_stock

    return pd.DataFrame(BLEV)


def size(date):
    # 获取最近一个交易日
    latest_trading_date = str(rqdatac.get_previous_trading_date(datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)))

    query = rqdatac.query(rqdatac.fundamentals.eod_derivative_indicator.market_cap)
    market_cap_series = rqdatac.get_fundamentals(query,entry_date=latest_trading_date,interval='1d')['market_cap'].T

    size_factor = pd.DataFrame(index=market_cap_series.index,columns=['size'])
    size_factor['size'] = [math.log(market_cap_series.loc[stock].values[0]) for stock in market_cap_series.index.tolist()]
    return size_factor


date = '2018-02-02'

mlev = market_leverage(date)
dtoa = debt_to_asset(date)
blev = book_leverage(date)

leverage = pd.DataFrame(index=mlev.index,columns=['leverage'])
leverage['leverage']=[ mlev.loc[stock].values[0]*0.38+dtoa.loc[stock].values[0]*0.35+blev.loc[stock].values[0]*0.27 for stock in leverage.index.tolist()]

# leverage缺失值过多，需要对缺失值进行处理
# 根据Barra的缺失值处理逻辑对leverage缺失值进行处理
for stock in mlev.index.tolist():
    if str(mlev.loc[stock].values[0]) != 'nan':
        if str(dtoa.loc[stock].values[0]) != 'nan':
            if str(blev.loc[stock].values[0]) != 'nan':
                leverage['leverage'][stock] = mlev.loc[stock].values[0]*0.38+dtoa.loc[stock].values[0]*0.35+blev.loc[stock].values[0]*0.27
            else:
                leverage['leverage'][stock] = mlev.loc[stock].values[0]*(38/73)+dtoa.loc[stock].values[0]*(35/73)
        elif str(blev.loc[stock].values[0]) != 'nan':
            leverage['leverage'][stock] = mlev.loc[stock].values[0] * (38 / 65) + blev.loc[stock].values[0] * (27 / 65)
        else:
            leverage['leverage'][stock] = mlev.loc[stock].values[0]
    else:
        if str(dtoa.loc[stock].values[0]) != 'nan':
            if str(blev.loc[stock].values[0]) != 'nan':
                leverage['leverage'][stock] = dtoa.loc[stock].values[0] * (35 / 62) + blev.loc[stock].values[0] * (27 / 62)
            else:
                leverage['leverage'][stock] = dtoa.loc[stock].values[0]
        else:
            leverage['leverage'][stock] = blev.loc[stock].values[0]

leverage.to_csv('/Users/rice/Desktop/leverage.csv', index=True, na_rep='NaN', header=True)

