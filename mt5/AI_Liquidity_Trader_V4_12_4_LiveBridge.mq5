#property strict
#property version   "4.12.4"
#property description "AI Liquidity Trader V4.12 - Universal Trading Guardian"

#include <Trade/Trade.mqh>
CTrade trade;

enum AssetModeEnum { ASSET_AUTO=0, ASSET_FOREX=1, ASSET_GOLD=2, ASSET_USOIL=3, ASSET_CRYPTO=4 };

enum SignalState { STATE_WAIT=0, STATE_BUY=1, STATE_SELL=2 };

input AssetModeEnum AssetMode=ASSET_AUTO;
input double CryptoMaxSpreadATRPercent=12.0;
input ENUM_TIMEFRAMES SignalTF=PERIOD_M15;
input ENUM_TIMEFRAMES ConfirmTF=PERIOD_H1;
input int FastEMA=50;
input int SlowEMA=200;
input int RSIPeriod=14;
input int ATRPeriod=14;
input int ADXPeriod=14;
input double MinADX=18.0;
input int SwingLookback=80;
input int MinSignalStrength=63;
input int TradeReadyStrength=70;
input int MinScoreGap=6;
input bool Use15MinForecast=true;
input int ForecastMinutes=15;
input int ForecastMinConfidence=63;
input int ForecastConfirmConfidence=70;
input int ForecastZoneOpacity=45; // 0=fully transparent, 255=solid
input double ForecastZoneATRBuffer=0.25;
input bool RequireHTFAlignment=false;
input bool RequireStructureAlignment=false;
input bool UseNewsFilter=true;
input int NewsBlockMinutes=15;
input int NewsScanHours=24;
input bool UseAssetProfile=true;

input double ATR_Stop_Multiplier=1.5;
input double RiskRewardTP1=1.5;
input double RiskRewardTP2=2.5;

input bool AllowAlgoTrading=false;
input bool UseRiskPercent=true;
input double RiskPercent=1.0;
input double FixedLot=0.01;
input bool UseMarginGuard=true;
input double MaxMarginUsePercent=25.0;
input double MinProjectedMarginLevel=200.0;
input int MaxOpenTrades=1;

// TRADING GUARDIAN: protects the account before an automated trade is allowed
input bool UseTradingGuardian=true;
input double MaxDailyLossPercent=3.0;
input double MaxDailyLossMoney=0.0; // 0 = percentage only
input double MaxEquityDrawdownPercent=10.0;
input int MaxTradesPerDay=3;
input int MaxLosingTradesPerDay=2;
input int LossCooldownMinutes=60;
input bool BlockIfGuardianWarning=true;
input bool EmergencyCloseEAOrders=false; // OFF by default
input bool GuardianAccountWide=true;

input ulong MagicNumber=46001;
input int MaxSpreadPoints=30;

input bool ShowDashboard=true;
input bool ShowVerticalConfirmation=true;
input bool DrawSupportResistance=true;
input bool DrawZones=true;
input bool DrawSignalArrows=true;
input bool ShowPreTradeLevels=true;
input bool DrawLiquidityFlow=true;
input bool DrawMarketDirection=true;
input bool DrawStructureBreaks=true;
input bool DrawOrderBlocks=true;
input bool ShowEntryMap=true;
input int FlowLookback=60;
input bool ShowFlowSequence=true;
input bool ShowFlowLabels=true;
input int FlowScanBars=24;

input bool EnableAlerts=true;
input bool EnableSoundAlerts=true;
input bool EnablePushAlerts=true;
input bool EnableEarlyWarning=true;
input int AlertCooldownSeconds=60;
input string BuySound="V47_BUY.wav";
input string SellSound="V47_SELL.wav";
input string WaitSound="V47_WAIT.wav";

input int PanelX=15;
input int PanelY=15;
input int PanelWidth=380;
input int PanelHeight=650;

int hFast=INVALID_HANDLE,hSlow=INVALID_HANDLE,hRSI=INVALID_HANDLE,hATR=INVALID_HANDLE,hADX=INVALID_HANDLE,hFractals=INVALID_HANDLE;
int hFastHTF=INVALID_HANDLE,hSlowHTF=INVALID_HANDLE,hRSIHTF=INVALID_HANDLE,hADXHTF=INVALID_HANDLE;
string prefix="ALT_V4123_";
string assetName="FOREX";
double assetATRStop=1.5;
int assetMaxSpread=30;
bool assetIsCrypto=false;
datetime lastSignalBar=0;
datetime lastAlertBar=0;
string lastAlertKey="";
datetime lastAlertTime=0;
color GREEN=clrLimeGreen;
color RED=clrRed;
color YELLOW=clrGold;
color WHITE=clrWhite;

struct Levels { double support; double resistance; };
struct Analysis
{
   SignalState state;
   string bias;
   string htf;
   string structure;
   string liquidity;
   string momentum;
   string trend;
   string fvg;
   int buyScore;
   int sellScore;
   int strength;
   double entry;
   double sl;
   double tp1;
   double tp2;
   double rsi;
   double adx;
   double atr;
   bool spreadOK;
   bool newsBlocked;
   bool newsDataOK;
   string newsName;
   string newsCurrency;
   datetime newsTime;
   int newsMinutesAway;
   Levels lv;
   string reason;
   double balance;
   double equity;
   double marginUsed;
   double freeMargin;
   double marginLevel;
   double tradeMargin;
   double projectedMarginLevel;
   double lot;
   bool marginOK;
   bool guardianOK;
   double dailyStartBalance;
   double dailyRealizedPL;
   double dailyLossMoney;
   double dailyLossPct;
   double peakEquity;
   double drawdownPct;
   int tradesToday;
   int losingTradesToday;
   int lossCooldownMinutes;
   string guardianReason;
   double tickSize;
   double tickValue;
   double contractSize;
   double volumeMin;
   double volumeMax;
   double volumeStep;
   double spreadPoints;
   double spreadPercentATR;
   int readiness;
   string readinessReason;
   string forecastDirection;
   string forecastPath;
   int forecastConfidence;
   datetime forecastExpiry;
};

string DetectAsset()
{
   string u=_Symbol; StringToUpper(u);
   if(AssetMode==ASSET_FOREX) return "FOREX";
   if(AssetMode==ASSET_GOLD) return "GOLD";
   if(AssetMode==ASSET_USOIL) return "USOIL";
   if(AssetMode==ASSET_CRYPTO) return "CRYPTO";
   if(StringFind(u,"XAU")>=0 || StringFind(u,"GOLD")>=0) return "GOLD";
   if(StringFind(u,"USOIL")>=0 || StringFind(u,"WTI")>=0 || StringFind(u,"XTI")>=0 || StringFind(u,"BRENT")>=0 || StringFind(u,"UKOIL")>=0 || StringFind(u,"XBR")>=0) return "USOIL";
   string crypto[]={"BTC","ETH","SOL","XRP","DOGE","LTC","ADA","BNB","AVAX","LINK","DOT","TRX","BCH","UNI","MATIC","SHIB","ATOM","ETC","XLM","NEAR","APT","ARB","OP","SUI"};
   for(int i=0;i<ArraySize(crypto);i++) if(StringFind(u,crypto[i])>=0) return "CRYPTO";
   return "FOREX";
}

void ApplyAssetProfile()
{
   assetName=DetectAsset();
   assetIsCrypto=(assetName=="CRYPTO");
   assetATRStop=ATR_Stop_Multiplier;
   assetMaxSpread=MaxSpreadPoints;
   if(!UseAssetProfile) return;
   if(assetName=="GOLD") { assetATRStop=MathMax(1.8,ATR_Stop_Multiplier); assetMaxSpread=MathMax(80,MaxSpreadPoints); }
   else if(assetName=="USOIL") { assetATRStop=MathMax(2.0,ATR_Stop_Multiplier); assetMaxSpread=MathMax(100,MaxSpreadPoints); }
   else if(assetName=="CRYPTO") { assetATRStop=MathMax(2.0,ATR_Stop_Multiplier); assetMaxSpread=MathMax(300,MaxSpreadPoints); }
   else { assetATRStop=MathMax(1.3,ATR_Stop_Multiplier); assetMaxSpread=MathMax(20,MaxSpreadPoints); }
}

double Buf(int handle,int buffer,int shift)
{
   double a[1];
   if(handle==INVALID_HANDLE || CopyBuffer(handle,buffer,shift,1,a)!=1) return EMPTY_VALUE;
   return a[0];
}

double PriceNow(bool buy)
{
   MqlTick t;
   if(!SymbolInfoTick(_Symbol,t)) return 0.0;
   return buy?t.ask:t.bid;
}

double N(double p){ return NormalizeDouble(p,(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS)); }

void ReadSymbolSpecs(Analysis &a)
{
   a.tickSize=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   a.tickValue=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   a.contractSize=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_CONTRACT_SIZE);
   a.volumeMin=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   a.volumeMax=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   a.volumeStep=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   long sp=SymbolInfoInteger(_Symbol,SYMBOL_SPREAD);
   a.spreadPoints=(sp>=0?(double)sp:0.0);
   a.spreadPercentATR=0.0;
   if(point>0.0 && a.atr>0.0) a.spreadPercentATR=((a.spreadPoints*point)/a.atr)*100.0;
}

string BuildDecisionReason(const Analysis &a)
{
   if(a.newsBlocked) return "BLOCKED: high-impact news";
   if(!a.newsDataOK && UseNewsFilter && !assetIsCrypto) return "CHECK: news calendar unavailable";
   if(!a.spreadOK) return "BLOCKED: spread too high";
   if(!a.guardianOK) return "BLOCKED: "+a.guardianReason;
   if((a.state==STATE_BUY || a.state==STATE_SELL) && !a.marginOK) return "WARNING: margin guard blocks execution";
   int gap=MathAbs(a.buyScore-a.sellScore);
   if(a.strength<MinSignalStrength) return "WAIT: strength "+IntegerToString(a.strength)+"/100 < "+IntegerToString(MinSignalStrength);
   if(gap<MinScoreGap) return "WAIT: BUY/SELL gap too small ("+IntegerToString(gap)+")";
   if(a.buyScore>a.sellScore) return "WAIT: bullish confirmation incomplete";
   if(a.sellScore>a.buyScore) return "WAIT: bearish confirmation incomplete";
   return "WAIT: evidence mixed";
}

void CalculateReadiness(Analysis &a)
{
   int score=0;
   if(a.spreadOK) score+=15;
   if(!a.newsBlocked && (a.newsDataOK || assetIsCrypto)) score+=15;
   if(a.guardianOK) score+=20;
   if(a.marginOK) score+=20;
   if(a.strength>=MinSignalStrength) score+=15;
   if(MathAbs(a.buyScore-a.sellScore)>=MinScoreGap) score+=15;
   a.readiness=score;
   if(!a.guardianOK) a.readinessReason=a.guardianReason;
   else if(!a.spreadOK) a.readinessReason="Spread protection";
   else if(a.newsBlocked) a.readinessReason="News protection";
   else if(a.strength<MinSignalStrength) a.readinessReason="Signal strength too low";
   else if(MathAbs(a.buyScore-a.sellScore)<MinScoreGap) a.readinessReason="Direction gap too small";
   else if(!a.marginOK) a.readinessReason="Margin protection";
   else a.readinessReason="Ready when signal is confirmed";
}

bool SpreadOK()
{
   long sp=SymbolInfoInteger(_Symbol,SYMBOL_SPREAD);
   if(sp<0) return false;
   if(!assetIsCrypto) return sp<=assetMaxSpread;
   double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   double atr=Buf(hATR,0,0);
   if(point<=0.0 || atr==EMPTY_VALUE || atr<=0.0) return sp<=assetMaxSpread;
   double spreadPrice=(double)sp*point;
   double maxByATR=atr*(CryptoMaxSpreadATRPercent/100.0);
   return sp<=assetMaxSpread && spreadPrice<=maxByATR;
}

bool GetNewsInfo(string &name,string &currency,datetime &eventTime,int &minutesAway,bool &dataOK)
{
   name=""; currency=""; eventTime=0; minutesAway=0; dataOK=true;
   if(!UseNewsFilter || MQLInfoInteger(MQL_TESTER)) return false;
   datetime now=TimeTradeServer(); if(now<=0) now=TimeCurrent();
   int scan=MathMax(1,NewsScanHours)*3600;
   datetime from=now-scan;
   datetime to=now+scan;
   string currencies[2]; int count=0;
   if(assetName=="CRYPTO") return false;
   if(assetName=="GOLD" || assetName=="USOIL") currencies[count++]="USD";
   else
   {
      string base=SymbolInfoString(_Symbol,SYMBOL_CURRENCY_BASE);
      string profit=SymbolInfoString(_Symbol,SYMBOL_CURRENCY_PROFIT);
      if(base!="") currencies[count++]=base;
      if(profit!="" && profit!=base && count<2) currencies[count++]=profit;
   }
   long bestAbs=2147483647;
   bool blocked=false;
   for(int c=0;c<count;c++)
   {
      MqlCalendarValue vals[];
      ResetLastError();
      int n=CalendarValueHistory(vals,from,to,NULL,currencies[c]);
      if(n<0) { dataOK=false; continue; }
      for(int i=0;i<n;i++)
      {
         MqlCalendarEvent ev;
         if(!CalendarEventById(vals[i].event_id,ev)) continue;
         if(ev.importance!=CALENDAR_IMPORTANCE_HIGH) continue;
         long diff=(long)vals[i].time-(long)now;
         long ad=diff<0?-diff:diff;
         if(ad<bestAbs)
         {
            bestAbs=ad; name=ev.name; currency=currencies[c]; eventTime=vals[i].time;
         }
         if(ad <= (long)NewsBlockMinutes*60) blocked=true;
      }
   }
   if(eventTime>0) minutesAway=(int)MathRound(((double)((long)eventTime-(long)now))/60.0);
   return blocked;
}

bool HighImpactNewsBlocked()
{
   string n,c; datetime t; int m; bool ok;
   return GetNewsInfo(n,c,t,m,ok);
}

string StructureText()
{
   double highs[], lows[]; ArrayResize(highs,3); ArrayResize(lows,3); ArrayInitialize(highs,0.0); ArrayInitialize(lows,0.0);
   int hk=0,lk=0;
   double up[],dn[];
   ArraySetAsSeries(up,true); ArraySetAsSeries(dn,true);
   int cu=CopyBuffer(hFractals,0,2,120,up);
   int cd=CopyBuffer(hFractals,1,2,120,dn);
   if(cu>0) for(int i=0;i<cu && hk<3;i++) if(up[i]!=EMPTY_VALUE && up[i]>0) highs[hk++]=up[i];
   if(cd>0) for(int i=0;i<cd && lk<3;i++) if(dn[i]!=EMPTY_VALUE && dn[i]>0) lows[lk++]=dn[i];
   if(hk<2 || lk<2) return "MIXED";
   bool hh=highs[0]>highs[1], lh=highs[0]<highs[1];
   bool hl=lows[0]>lows[1], ll=lows[0]<lows[1];
   if(hh&&hl) return "HH + HL";
   if(lh&&ll) return "LH + LL";
   if(hl) return "HL";
   if(lh) return "LH";
   return "MIXED";
}

Levels FindLevels()
{
   Levels lv; lv.support=0; lv.resistance=0;
   double price=Buf(hFast,0,1); if(price==EMPTY_VALUE) price=iClose(_Symbol,SignalTF,1);
   double up[],dn[]; ArraySetAsSeries(up,true);ArraySetAsSeries(dn,true);
   int cu=CopyBuffer(hFractals,0,2,MathMin(SwingLookback,120),up);
   int cd=CopyBuffer(hFractals,1,2,MathMin(SwingLookback,120),dn);
   if(cu>0) for(int i=0;i<cu;i++) if(up[i]!=EMPTY_VALUE && up[i]>price){lv.resistance=up[i];break;}
   if(cd>0) for(int i=0;i<cd;i++) if(dn[i]!=EMPTY_VALUE && dn[i]<price){lv.support=dn[i];break;}
   return lv;
}

string Liquidity(const Levels &lv,int &buyPts,int &sellPts)
{
   buyPts=0;sellPts=0;
   double hi=iHigh(_Symbol,SignalTF,2),lo=iLow(_Symbol,SignalTF,2);
   double cl=iClose(_Symbol,SignalTF,1);
   string out="WAIT";
   if(lv.resistance>0 && hi>lv.resistance && cl<lv.resistance){sellPts=18;out="HIGH SWEEP / REJECT";}
   else if(lv.support>0 && lo<lv.support && cl>lv.support){buyPts=18;out="LOW SWEEP / RECLAIM";}
   else if(lv.support>0 && MathAbs(cl-lv.support)<=Buf(hATR,0,1)*0.6){buyPts=7;out="NEAR SUPPORT";}
   else if(lv.resistance>0 && MathAbs(cl-lv.resistance)<=Buf(hATR,0,1)*0.6){sellPts=7;out="NEAR RESISTANCE";}
   return out;
}

string FVG(int &buyPts,int &sellPts)
{
   buyPts=0;sellPts=0;
   double atr=Buf(hATR,0,1); if(atr==EMPTY_VALUE) return "NONE";
   double c=iClose(_Symbol,SignalTF,1);
   for(int i=1;i<=8;i++)
   {
      double hOld=iHigh(_Symbol,SignalTF,i+2),lOld=iLow(_Symbol,SignalTF,i+2);
      double hNew=iHigh(_Symbol,SignalTF,i),lNew=iLow(_Symbol,SignalTF,i);
      if(lNew>hOld && (lNew-hOld)>=atr*0.10 && c>=hOld && c<=lNew){buyPts=10;return "BULLISH FVG";}
      if(hNew<lOld && (lOld-hNew)>=atr*0.10 && c>=hNew && c<=lOld){sellPts=10;return "BEARISH FVG";}
   }
   return "NONE";
}

bool HTFBullish(){ double f=Buf(hFastHTF,0,1),s=Buf(hSlowHTF,0,1),r=Buf(hRSIHTF,0,1); return f!=EMPTY_VALUE&&s!=EMPTY_VALUE&&r!=EMPTY_VALUE&&f>s&&r>=50; }
bool HTFBearish(){ double f=Buf(hFastHTF,0,1),s=Buf(hSlowHTF,0,1),r=Buf(hRSIHTF,0,1); return f!=EMPTY_VALUE&&s!=EMPTY_VALUE&&r!=EMPTY_VALUE&&f<s&&r<=50; }

void Calculate15MinForecast(Analysis &a)
{
   a.forecastDirection="NEUTRAL";
   a.forecastPath="MIXED";
   a.forecastConfidence=0;
   a.forecastExpiry=TimeCurrent()+ForecastMinutes*60;
   if(!Use15MinForecast) return;

   double c0=iClose(_Symbol,SignalTF,0), c1=iClose(_Symbol,SignalTF,1), c2=iClose(_Symbol,SignalTF,2);
   double f0=Buf(hFast,0,0), f1=Buf(hFast,0,1), s0=Buf(hSlow,0,0), r0=Buf(hRSI,0,0), adx0=Buf(hADX,0,0);
   double pdi=Buf(hADX,1,0), mdi=Buf(hADX,2,0), atr=Buf(hATR,0,0);
   if(c0<=0||c1<=0||c2<=0||f0<=0||s0<=0||atr<=0) return;

   int bull=0,bear=0;
   if(c0>f0) bull+=20; else if(c0<f0) bear+=20;
   if(f0>s0) bull+=20; else if(f0<s0) bear+=20;
   if(f0>f1) bull+=12; else if(f0<f1) bear+=12;
   if(c0>c1 && c1>=c2) bull+=15; else if(c0<c1 && c1<=c2) bear+=15;
   if(r0>=55 && r0<75) bull+=10; else if(r0<=45 && r0>25) bear+=10;
   if(adx0>=MinADX && pdi>mdi) bull+=15; else if(adx0>=MinADX && mdi>pdi) bear+=15;
   if(c0>c1+atr*0.10) bull+=8; else if(c0<c1-atr*0.10) bear+=8;

   int best=MathMax(bull,bear);
   int confidence=(int)MathRound(MathMin(100.0,best));
   a.forecastConfidence=confidence;
   if(bull>bear && confidence>=ForecastMinConfidence) a.forecastDirection="BULLISH";
   else if(bear>bull && confidence>=ForecastMinConfidence) a.forecastDirection="BEARISH";
   else a.forecastDirection="NEUTRAL";

   if(a.forecastDirection=="BULLISH")
      a.forecastPath=(c0>f0 && f0>s0)?"CONTINUATION":"PULLBACK / CONTINUATION";
   else if(a.forecastDirection=="BEARISH")
      a.forecastPath=(c0<f0 && f0<s0)?"CONTINUATION":"PULLBACK / CONTINUATION";
   else
      a.forecastPath="WAIT FOR DIRECTION";
}

void CalculateSignal(Analysis &a)
{
   a.state=STATE_WAIT;a.bias="NEUTRAL";a.htf="MIXED";a.structure="MIXED";a.liquidity="WAIT";a.momentum="WAIT";a.trend="NEUTRAL";a.fvg="NONE";
   a.buyScore=0;a.sellScore=0;a.strength=0;a.entry=0;a.sl=0;a.tp1=0;a.tp2=0;a.rsi=0;a.adx=0;a.atr=0;
   a.tickSize=0;a.tickValue=0;a.contractSize=0;a.volumeMin=0;a.volumeMax=0;a.volumeStep=0;a.spreadPoints=0;a.spreadPercentATR=0;a.readiness=0;a.readinessReason="Loading...";
   a.marginOK=true; a.guardianOK=true; a.guardianReason="GUARDIAN OK";
   a.spreadOK=SpreadOK();
   a.newsName=""; a.newsCurrency=""; a.newsTime=0; a.newsMinutesAway=0; a.newsDataOK=true;
   a.newsBlocked=GetNewsInfo(a.newsName,a.newsCurrency,a.newsTime,a.newsMinutesAway,a.newsDataOK);
   a.lv=FindLevels();a.reason="Waiting for live market confirmation.";

   // V4.7 is intentionally LIVE: shift 0 follows the current forming candle and current indicator values.
   double close0=iClose(_Symbol,SignalTF,0), open0=iOpen(_Symbol,SignalTF,0);
   double close1=iClose(_Symbol,SignalTF,1);
   double fast=Buf(hFast,0,0), slow=Buf(hSlow,0,0), rsi=Buf(hRSI,0,0), atr=Buf(hATR,0,0), adx=Buf(hADX,0,0), plus=Buf(hADX,1,0), minus=Buf(hADX,2,0);
   if(close0<=0||fast==EMPTY_VALUE||slow==EMPTY_VALUE||rsi==EMPTY_VALUE||atr==EMPTY_VALUE||adx==EMPTY_VALUE||plus==EMPTY_VALUE||minus==EMPTY_VALUE)
   {
      a.reason="LOADING INDICATORS...";
      return;
   }
   a.rsi=rsi;a.atr=atr;a.adx=adx;
   ReadSymbolSpecs(a);

   // Direction: current price versus both EMAs.
   bool priceBull=(close0>fast); bool priceBear=(close0<fast);
   bool trendBull=(fast>slow); bool trendBear=(fast<slow);
   if(priceBull){a.buyScore+=18;a.bias="BULLISH";} else if(priceBear){a.sellScore+=18;a.bias="BEARISH";}
   if(trendBull)a.buyScore+=14; else if(trendBear)a.sellScore+=14;

   // EMA slope keeps direction responsive without waiting for a new bar.
   double fastPrev=Buf(hFast,0,1),slowPrev=Buf(hSlow,0,1);
   if(fastPrev!=EMPTY_VALUE){ if(fast>fastPrev)a.buyScore+=8; else if(fast<fastPrev)a.sellScore+=8; }
   if(slowPrev!=EMPTY_VALUE){ if(slow>slowPrev)a.buyScore+=5; else if(slow<slowPrev)a.sellScore+=5; }

   // ADX/DI: trend strength plus direction.
   if(adx>=MinADX){
      if(plus>minus){a.buyScore+=12;a.trend="BULLISH";}
      else if(minus>plus){a.sellScore+=12;a.trend="BEARISH";}
      else a.trend="TRENDING / MIXED";
   } else a.trend="WEAK TREND";

   // RSI is treated as momentum, not as an automatic reversal signal.
   if(rsi>=52 && rsi<=72){a.buyScore+=12;a.momentum="RSI BUY";}
   else if(rsi<=48 && rsi>=28){a.sellScore+=12;a.momentum="RSI SELL";}
   else if(rsi>72){a.momentum="OVERBOUGHT"; if(priceBull)a.buyScore+=5;}
   else if(rsi<28){a.momentum="OVERSOLD"; if(priceBear)a.sellScore+=5;}
   else a.momentum="NEUTRAL";

   // Current candle and short-term price impulse.
   if(close0>open0)a.buyScore+=7;
   else if(close0<open0)a.sellScore+=7;
   if(close0>close1)a.buyScore+=6;
   else if(close0<close1)a.sellScore+=6;

   // Market structure is confirmation weight, not a hard gate.
   a.structure=StructureText();
   if(a.structure=="HH + HL")a.buyScore+=12;
   else if(a.structure=="HL")a.buyScore+=8;
   else if(a.structure=="LH + LL")a.sellScore+=12;
   else if(a.structure=="LH")a.sellScore+=8;

   int lb=0,ls=0; a.liquidity=Liquidity(a.lv,lb,ls); a.buyScore+=lb;a.sellScore+=ls;
   int fb=0,fs=0; a.fvg=FVG(fb,fs);a.buyScore+=fb;a.sellScore+=fs;

   bool hb=HTFBullish(), hs=HTFBearish();
   if(hb){a.htf="BULLISH";a.buyScore+=8;}
   else if(hs){a.htf="BEARISH";a.sellScore+=8;}

   // Spread and high-impact news remain the only hard safety gates.
   if(!a.spreadOK){a.state=STATE_WAIT;a.reason="SPREAD TOO HIGH";}
   else if(a.newsBlocked){a.state=STATE_WAIT;a.reason="HIGH IMPACT NEWS BLOCK";}

   int raw=MathMax(a.buyScore,a.sellScore);
   a.strength=(int)MathRound(MathMin(100.0,raw*100.0/120.0));
   int gap=MathAbs(a.buyScore-a.sellScore);

   bool buy=(a.buyScore>a.sellScore && gap>=MinScoreGap && a.strength>=MinSignalStrength);
   bool sell=(a.sellScore>a.buyScore && gap>=MinScoreGap && a.strength>=MinSignalStrength);
   if(a.newsBlocked||!a.spreadOK){buy=false;sell=false;}

   // Optional strict confirmation can still be enabled by the user.
   if(RequireHTFAlignment){if(buy&&!hb)buy=false;if(sell&&!hs)sell=false;}
   if(RequireStructureAlignment){if(buy&&!(a.structure=="HH + HL"||a.structure=="HL"))buy=false;if(sell&&!(a.structure=="LH + LL"||a.structure=="LH"))sell=false;}

   bool preBuy=(a.buyScore>a.sellScore && gap>=4);
   bool preSell=(a.sellScore>a.buyScore && gap>=4);
   double entry=PriceNow(preBuy);
   if(entry<=0)entry=close0;
   a.entry=entry;

   double stopDist=atr*assetATRStop;
   if(preBuy){
      double base=(a.lv.support>0&&a.lv.support<entry)?a.lv.support:entry-stopDist;
      a.sl=N(MathMin(base,entry-stopDist*0.65));
      double r=entry-a.sl;a.tp1=N(entry+r*RiskRewardTP1);a.tp2=N(entry+r*RiskRewardTP2);
   }else if(preSell){
      double base=(a.lv.resistance>0&&a.lv.resistance>entry)?a.lv.resistance:entry+stopDist;
      a.sl=N(MathMax(base,entry+stopDist*0.65));
      double r=a.sl-entry;a.tp1=N(entry-r*RiskRewardTP1);a.tp2=N(entry-r*RiskRewardTP2);
   }

   if(buy){a.state=STATE_BUY;a.reason="BUY LIVE: price + trend + momentum/confluence aligned.";}
   else if(sell){a.state=STATE_SELL;a.reason="SELL LIVE: price + trend + momentum/confluence aligned.";}
   else if(preBuy){a.state=STATE_WAIT;a.reason="BULLISH LIVE BIAS: confirmation building.";}
   else if(preSell){a.state=STATE_WAIT;a.reason="BEARISH LIVE BIAS: confirmation building.";}
   else {a.state=STATE_WAIT;a.reason="WAIT: live evidence is mixed.";}
   Calculate15MinForecast(a);
}

void DeleteObjects()
{
   for(int i=ObjectsTotal(0,-1,-1)-1;i>=0;i--){ string n=ObjectName(0,i,-1,-1); if(StringFind(n,prefix)==0) ObjectDelete(0,n); }
}

void SetLabel(string name,string text,int x,int y,color c,int size=9)
{
   if(ObjectFind(0,name)<0) ObjectCreate(0,name,OBJ_LABEL,0,0,0);
   ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE,x);ObjectSetInteger(0,name,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,size);ObjectSetString(0,name,OBJPROP_FONT,"Arial");
   ObjectSetInteger(0,name,OBJPROP_COLOR,c);ObjectSetString(0,name,OBJPROP_TEXT,text);
}

void SetBox(string name,int x,int y,int w,int h,color bg,color border)
{
   if(ObjectFind(0,name)<0) ObjectCreate(0,name,OBJ_RECTANGLE_LABEL,0,0,0);
   ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);ObjectSetInteger(0,name,OBJPROP_XDISTANCE,x);ObjectSetInteger(0,name,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,name,OBJPROP_XSIZE,w);ObjectSetInteger(0,name,OBJPROP_YSIZE,h);ObjectSetInteger(0,name,OBJPROP_BGCOLOR,bg);ObjectSetInteger(0,name,OBJPROP_BORDER_COLOR,border);ObjectSetInteger(0,name,OBJPROP_BACK,false);
}

void HLine(string name,double price,color c,ENUM_LINE_STYLE style=STYLE_DASH)
{
   if(price<=0)return;
   if(ObjectFind(0,name)<0)ObjectCreate(0,name,OBJ_HLINE,0,0,price);
   ObjectSetDouble(0,name,OBJPROP_PRICE,price);ObjectSetInteger(0,name,OBJPROP_COLOR,c);ObjectSetInteger(0,name,OBJPROP_STYLE,style);ObjectSetInteger(0,name,OBJPROP_WIDTH,2);ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
}

void DrawPanel(const Analysis &a)
{
   if(!ShowDashboard)return;
   MqlTick tick;SymbolInfoTick(_Symbol,tick);double live=tick.bid;
   color status=YELLOW;string state="WAIT / NO TRADE";
   if(a.state==STATE_BUY){status=GREEN;state=(a.strength>=TradeReadyStrength?"BUY — CONFIRMED":"BUY — DETECTED");}
   if(a.state==STATE_SELL){status=RED;state=(a.strength>=TradeReadyStrength?"SELL — CONFIRMED":"SELL — DETECTED");}
   SetBox(prefix+"BG",PanelX,PanelY,PanelWidth,PanelHeight,clrBlack,status);
   SetBox(prefix+"STATUS",PanelX+10,PanelY+10,PanelWidth-20,42,status,status);
   SetLabel(prefix+"TITLE",state,PanelX+24,PanelY+21,WHITE,13);
   SetLabel(prefix+"PRICE",assetName+" | "+_Symbol+" | LIVE "+DoubleToString(live,_Digits),PanelX+16,PanelY+62,WHITE,9);
   SetLabel(prefix+"BIAS","MARKET BIAS  "+a.bias,PanelX+16,PanelY+84,a.bias=="BULLISH"?GREEN:(a.bias=="BEARISH"?RED:YELLOW),10);
   SetLabel(prefix+"SCORE","SIGNAL STRENGTH  "+IntegerToString(a.strength)+"/100",PanelX+16,PanelY+106,status,10);
   SetLabel(prefix+"T1","Trend       "+a.trend,PanelX+16,PanelY+132,a.trend=="BULLISH"?GREEN:(a.trend=="BEARISH"?RED:YELLOW),9);
   SetLabel(prefix+"T2","HTF         "+a.htf,PanelX+16,PanelY+151,a.htf=="BULLISH"?GREEN:(a.htf=="BEARISH"?RED:YELLOW),9);
   SetLabel(prefix+"T3","Structure   "+a.structure,PanelX+16,PanelY+170,a.structure=="HH + HL"||a.structure=="HL"?GREEN:(a.structure=="LH + LL"||a.structure=="LH"?RED:YELLOW),9);
   SetLabel(prefix+"T4","Liquidity   "+a.liquidity,PanelX+16,PanelY+189,StringFind(a.liquidity,"LOW")>=0?GREEN:(StringFind(a.liquidity,"HIGH")>=0?RED:YELLOW),9);
   SetLabel(prefix+"T5","Momentum    "+a.momentum,PanelX+16,PanelY+208,StringFind(a.momentum,"BUY")>=0?GREEN:(StringFind(a.momentum,"SELL")>=0?RED:YELLOW),9);
   SetLabel(prefix+"T6","FVG         "+a.fvg,PanelX+16,PanelY+227,StringFind(a.fvg,"BULL")>=0?GREEN:(StringFind(a.fvg,"BEAR")>=0?RED:YELLOW),9);
   string spreadText="Spread      "+(a.spreadOK?"OK":"HIGH");
   if(assetIsCrypto) spreadText+="  "+DoubleToString(a.spreadPercentATR,1)+"% ATR";
   SetLabel(prefix+"T7",spreadText,PanelX+16,PanelY+246,a.spreadOK?GREEN:RED,8);
   SetLabel(prefix+"T8","News        "+(a.newsBlocked?"BLOCKED":"CLEAR"),PanelX+16,PanelY+265,a.newsBlocked?RED:GREEN,9);
   string newsLine="News detail  ";
   if(!a.newsDataOK) newsLine+="CALENDAR DATA UNAVAILABLE";
   else if(a.newsName=="") newsLine+="No high-impact event nearby";
   else
   {
      string when=(a.newsMinutesAway>0?"in "+IntegerToString(a.newsMinutesAway)+"m":(a.newsMinutesAway<0?IntegerToString(MathAbs(a.newsMinutesAway))+"m ago":"NOW"));
      newsLine+=a.newsCurrency+" | "+when;
   }
   SetLabel(prefix+"NEWS_DETAIL",newsLine,PanelX+16,PanelY+284,a.newsBlocked?RED:WHITE,8);
   if(a.newsName!="")
      SetLabel(prefix+"NEWS_NAME",StringSubstr(a.newsName,0,48),PanelX+16,PanelY+300,YELLOW,8);

   // Expanded Guardian block: separate rows prevent overlap.
   SetLabel(prefix+"GUARD", "GUARDIAN "+(a.guardianOK?"OK":"BLOCK: "+a.guardianReason),PanelX+16,PanelY+326,a.guardianOK?GREEN:RED,9);
   SetLabel(prefix+"RISK", "DAY LOSS "+DoubleToString(a.dailyLossPct,1)+"% | TRADES "+IntegerToString(a.tradesToday)+" | LOSSES "+IntegerToString(a.losingTradesToday),PanelX+16,PanelY+348,a.guardianOK?WHITE:RED,8);
   SetLabel(prefix+"DD", "PEAK DD "+DoubleToString(a.drawdownPct,1)+"% | COOLDOWN "+IntegerToString(a.lossCooldownMinutes)+"m",PanelX+16,PanelY+367,a.guardianOK?WHITE:RED,8);
   SetLabel(prefix+"MARGIN","MARGIN Free "+DoubleToString(a.freeMargin,2)+" | Level "+DoubleToString(a.marginLevel,0)+"%",PanelX+16,PanelY+386,a.marginOK?GREEN:YELLOW,8);
   SetLabel(prefix+"LOT","LOT "+DoubleToString(a.lot,2)+" | Req "+DoubleToString(a.tradeMargin,2)+" | Proj "+DoubleToString(a.projectedMarginLevel,0)+"%",PanelX+16,PanelY+405,a.marginOK?WHITE:YELLOW,8);
   SetLabel(prefix+"SPECS","Tick "+DoubleToString(a.tickSize,_Digits)+" | TV "+DoubleToString(a.tickValue,2)+" | Contract "+DoubleToString(a.contractSize,2),PanelX+16,PanelY+423,WHITE,7);
   SetLabel(prefix+"READY","READINESS "+IntegerToString(a.readiness)+"/100 | "+a.readinessReason,PanelX+16,PanelY+439,a.readiness>=80?GREEN:(a.readiness>=60?YELLOW:RED),8);
   SetLabel(prefix+"DETECT","DETECTION "+(a.strength>=MinSignalStrength?(a.bias=="BULLISH"?"BUY":(a.bias=="BEARISH"?"SELL":"WAIT")):"BUILDING")+" | threshold "+IntegerToString(MinSignalStrength)+"/100",PanelX+16,PanelY+458,a.strength>=MinSignalStrength?(a.bias=="BULLISH"?GREEN:(a.bias=="BEARISH"?RED:YELLOW)):YELLOW,8);
   color fc=(a.forecastDirection=="BULLISH"?GREEN:(a.forecastDirection=="BEARISH"?RED:YELLOW));
   SetLabel(prefix+"FC1","15M FORECAST  "+a.forecastDirection+"  "+IntegerToString(a.forecastConfidence)+"/100",PanelX+16,PanelY+478,fc,9);
   SetLabel(prefix+"FC2","PATH          "+a.forecastPath,PanelX+16,PanelY+498,fc,8);
   SetLabel(prefix+"FC3","HORIZON       "+IntegerToString(ForecastMinutes)+" MIN | "+(a.forecastConfidence>=ForecastConfirmConfidence?"CONFIRMED":"DETECTING"),PanelX+16,PanelY+517,fc,8);
   SetLabel(prefix+"E","ENTRY   "+DoubleToString(a.entry,_Digits),PanelX+16,PanelY+540,WHITE,9);
   SetLabel(prefix+"S","SL      "+DoubleToString(a.sl,_Digits),PanelX+16,PanelY+562,RED,9);
   SetLabel(prefix+"P","TP1     "+DoubleToString(a.tp1,_Digits)+"   TP2 "+DoubleToString(a.tp2,_Digits),PanelX+16,PanelY+584,GREEN,9);
   SetLabel(prefix+"WHY","WHY: "+StringSubstr(a.reason,0,58),PanelX+16,PanelY+625,YELLOW,8);
}


void DrawFVGZone()
{
   string bull=prefix+"FVG_BULL";
   string bear=prefix+"FVG_BEAR";
   string bullTxt=prefix+"FVG_BULL_TXT";
   string bearTxt=prefix+"FVG_BEAR_TXT";
   ObjectDelete(0,bull); ObjectDelete(0,bear);
   ObjectDelete(0,bullTxt); ObjectDelete(0,bearTxt);
   if(!DrawZones) return;

   double atr=Buf(hATR,0,1);
   if(atr==EMPTY_VALUE || atr<=0) return;
   int scan=MathMax(1,MathMin(FlowScanBars,30));
   datetime right=iTime(_Symbol,SignalTF,0)+PeriodSeconds(SignalTF)*8;

   for(int i=1;i<=scan;i++)
   {
      double hOld=iHigh(_Symbol,SignalTF,i+2), lOld=iLow(_Symbol,SignalTF,i+2);
      double hNew=iHigh(_Symbol,SignalTF,i),   lNew=iLow(_Symbol,SignalTF,i);
      datetime left=iTime(_Symbol,SignalTF,i+2);

      if(lNew>hOld && (lNew-hOld)>=atr*0.10)
      {
         if(ObjectCreate(0,bull,OBJ_RECTANGLE,0,left,hOld,right,lNew))
         {
            ObjectSetInteger(0,bull,OBJPROP_COLOR,GREEN);
            ObjectSetInteger(0,bull,OBJPROP_STYLE,STYLE_SOLID);
            ObjectSetInteger(0,bull,OBJPROP_WIDTH,2);
            ObjectSetInteger(0,bull,OBJPROP_FILL,true);
            ObjectSetInteger(0,bull,OBJPROP_BACK,true);
            ObjectSetInteger(0,bull,OBJPROP_SELECTABLE,false);
            ObjectSetString(0,bull,OBJPROP_TOOLTIP,"BULLISH FVG");
            SetText(bullTxt,left,lNew,"FVG  BUY ZONE",GREEN,9);
         }
         return;
      }
      if(hNew<lOld && (lOld-hNew)>=atr*0.10)
      {
         if(ObjectCreate(0,bear,OBJ_RECTANGLE,0,left,lOld,right,hNew))
         {
            ObjectSetInteger(0,bear,OBJPROP_COLOR,RED);
            ObjectSetInteger(0,bear,OBJPROP_STYLE,STYLE_SOLID);
            ObjectSetInteger(0,bear,OBJPROP_WIDTH,2);
            ObjectSetInteger(0,bear,OBJPROP_FILL,true);
            ObjectSetInteger(0,bear,OBJPROP_BACK,true);
            ObjectSetInteger(0,bear,OBJPROP_SELECTABLE,false);
            ObjectSetString(0,bear,OBJPROP_TOOLTIP,"BEARISH FVG");
            SetText(bearTxt,left,lOld,"FVG  SELL ZONE",RED,9);
         }
         return;
      }
   }
}

//====================== V4.8 LIVE CHART INTELLIGENCE ======================
void SetTrend(string name,datetime t1,double p1,datetime t2,double p2,color c,ENUM_LINE_STYLE style=STYLE_SOLID,int width=2,bool rayRight=false)
{
   if(t1<=0 || t2<=0 || p1<=0 || p2<=0) return;
   if(ObjectFind(0,name)<0) ObjectCreate(0,name,OBJ_TREND,0,t1,p1,t2,p2);
   else { ObjectMove(0,name,0,t1,p1); ObjectMove(0,name,1,t2,p2); }
   ObjectSetInteger(0,name,OBJPROP_COLOR,c);
   ObjectSetInteger(0,name,OBJPROP_STYLE,style);
   ObjectSetInteger(0,name,OBJPROP_WIDTH,width);
   ObjectSetInteger(0,name,OBJPROP_RAY_RIGHT,rayRight);
   ObjectSetInteger(0,name,OBJPROP_BACK,false);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
}

void SetText(string name,datetime t,double p,string text,color c,int size=9)
{
   if(t<=0 || p<=0) return;
   if(ObjectFind(0,name)<0) ObjectCreate(0,name,OBJ_TEXT,0,t,p);
   else ObjectMove(0,name,0,t,p);
   ObjectSetString(0,name,OBJPROP_TEXT,text);
   ObjectSetString(0,name,OBJPROP_FONT,"Arial");
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,size);
   ObjectSetInteger(0,name,OBJPROP_COLOR,c);
   ObjectSetInteger(0,name,OBJPROP_ZORDER,10);
   ObjectSetInteger(0,name,OBJPROP_ANCHOR,ANCHOR_LEFT);
   ObjectSetInteger(0,name,OBJPROP_BACK,false);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
}

void SetChartArrow(string name,datetime t,double p,bool up,color c)
{
   if(t<=0 || p<=0) return;
   ENUM_OBJECT typ=up?OBJ_ARROW_UP:OBJ_ARROW_DOWN;
   if(ObjectFind(0,name)<0) ObjectCreate(0,name,typ,0,t,p);
   else ObjectMove(0,name,0,t,p);
   ObjectSetInteger(0,name,OBJPROP_COLOR,c);
   ObjectSetInteger(0,name,OBJPROP_WIDTH,5);
   ObjectSetInteger(0,name,OBJPROP_BACK,false);
   ObjectSetInteger(0,name,OBJPROP_ZORDER,20);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
}

bool FindRecentFractals(double &lastHigh,double &prevHigh,datetime &lastHighT,datetime &prevHighT,double &lastLow,double &prevLow,datetime &lastLowT,datetime &prevLowT)
{
   lastHigh=prevHigh=lastLow=prevLow=0; lastHighT=prevHighT=lastLowT=prevLowT=0;
   double up[],dn[]; datetime times[];
   ArrayResize(up,MathMin(FlowLookback,120)); ArrayResize(dn,MathMin(FlowLookback,120)); ArrayResize(times,MathMin(FlowLookback,120));
   int n=ArraySize(up);
   int cu=CopyBuffer(hFractals,0,2,n,up);
   int cd=CopyBuffer(hFractals,1,2,n,dn);
   int ct=CopyTime(_Symbol,SignalTF,2,n,times);
   if(cu<=0 || cd<=0 || ct<=0) return false;
   for(int i=0;i<cu;i++)
   {
      if(up[i]!=EMPTY_VALUE && up[i]>0)
      {
         if(lastHigh==0){lastHigh=up[i];lastHighT=times[i];}
         else if(prevHigh==0){prevHigh=up[i];prevHighT=times[i];break;}
      }
   }
   for(int i=0;i<cd;i++)
   {
      if(dn[i]!=EMPTY_VALUE && dn[i]>0)
      {
         if(lastLow==0){lastLow=dn[i];lastLowT=times[i];}
         else if(prevLow==0){prevLow=dn[i];prevLowT=times[i];break;}
      }
   }
   return (lastHigh>0 || lastLow>0);
}

void DrawOrderBlockMap(const Analysis &a)
{
   string bull=prefix+"OB_BULL", bear=prefix+"OB_BEAR";
   ObjectDelete(0,bull); ObjectDelete(0,bear);
   if(!DrawOrderBlocks) return;
   double atr=a.atr; if(atr<=0) return;
   // Simple, transparent order-block heuristic: last opposite candle before a strong move.
   for(int i=1;i<=6;i++)
   {
      double o=iOpen(_Symbol,SignalTF,i), c=iClose(_Symbol,SignalTF,i), h=iHigh(_Symbol,SignalTF,i), l=iLow(_Symbol,SignalTF,i);
      double oPrev=iOpen(_Symbol,SignalTF,i+1), cPrev=iClose(_Symbol,SignalTF,i+1);
      if(c>o && c-o>=atr*0.55 && cPrev<oPrev)
      {
         datetime t1=iTime(_Symbol,SignalTF,i+1), t2=iTime(_Symbol,SignalTF,0)+PeriodSeconds(SignalTF)*4;
         if(ObjectCreate(0,bull,OBJ_RECTANGLE,0,t1,oPrev,t2,l))
         {
            ObjectSetInteger(0,bull,OBJPROP_COLOR,GREEN); ObjectSetInteger(0,bull,OBJPROP_FILL,true); ObjectSetInteger(0,bull,OBJPROP_BACK,true); ObjectSetInteger(0,bull,OBJPROP_WIDTH,1); ObjectSetString(0,bull,OBJPROP_TOOLTIP,"BULLISH ORDER BLOCK");
         }
         return;
      }
      if(c<o && o-c>=atr*0.55 && cPrev>oPrev)
      {
         datetime t1=iTime(_Symbol,SignalTF,i+1), t2=iTime(_Symbol,SignalTF,0)+PeriodSeconds(SignalTF)*4;
         if(ObjectCreate(0,bear,OBJ_RECTANGLE,0,t1,oPrev,t2,h))
         {
            ObjectSetInteger(0,bear,OBJPROP_COLOR,RED); ObjectSetInteger(0,bear,OBJPROP_FILL,true); ObjectSetInteger(0,bear,OBJPROP_BACK,true); ObjectSetInteger(0,bear,OBJPROP_WIDTH,1); ObjectSetString(0,bear,OBJPROP_TOOLTIP,"BEARISH ORDER BLOCK");
         }
         return;
      }
   }
}

void DrawStructureAndLiquidity(const Analysis &a)
{
   if(!DrawMarketDirection && !DrawLiquidityFlow && !DrawStructureBreaks) return;
   double lh,ph,ll,pl; datetime lht,pht,llt,plt;
   if(!FindRecentFractals(lh,ph,lht,pht,ll,pl,llt,plt)) return;
   datetime nowT=iTime(_Symbol,SignalTF,0); double live=PriceNow(a.state!=STATE_SELL);
   if(live<=0) live=iClose(_Symbol,SignalTF,0);
   color dirColor=(a.bias=="BULLISH"?GREEN:(a.bias=="BEARISH"?RED:YELLOW));

   if(DrawMarketDirection)
   {
      if(lh>0 && ph>0) SetTrend(prefix+"DIR_HIGH",pht,ph,lht,lh,dirColor,STYLE_DASH,2,true);
      if(ll>0 && pl>0) SetTrend(prefix+"DIR_LOW",plt,pl,llt,ll,dirColor,STYLE_DASH,2,true);
      string flow=(a.bias=="BULLISH"?"BULLISH FLOW":(a.bias=="BEARISH"?"BEARISH FLOW":"MIXED FLOW"));
      SetText(prefix+"FLOW_TEXT",nowT,live,flow+"  "+IntegerToString(a.strength)+"/100",dirColor,10);
   }

   if(DrawLiquidityFlow)
   {
      if(a.liquidity=="LOW SWEEP / RECLAIM" && ll>0)
      {
         datetime st=iTime(_Symbol,SignalTF,1); double sp=iLow(_Symbol,SignalTF,1);
         SetChartArrow(prefix+"LIQ_BUY",st,sp-a.atr*0.25,true,GREEN);
         SetText(prefix+"LIQ_BUY_TXT",st,sp-a.atr*0.45,"LIQUIDITY SWEEP → RECLAIM",GREEN,8);
         SetTrend(prefix+"FLOW_BUY",st,sp,nowT,live,GREEN,STYLE_SOLID,2,false);
      }
      else if(a.liquidity=="HIGH SWEEP / REJECT" && lh>0)
      {
         datetime st=iTime(_Symbol,SignalTF,1); double sp=iHigh(_Symbol,SignalTF,1);
         SetChartArrow(prefix+"LIQ_SELL",st,sp+a.atr*0.25,false,RED);
         SetText(prefix+"LIQ_SELL_TXT",st,sp+a.atr*0.45,"LIQUIDITY SWEEP → REJECT",RED,8);
         SetTrend(prefix+"FLOW_SELL",st,sp,nowT,live,RED,STYLE_SOLID,2,false);
      }
   }

   if(DrawStructureBreaks)
   {
      double c=iClose(_Symbol,SignalTF,0);
      if(lh>0 && c>lh)
      {
         SetText(prefix+"BOS_BULL_TXT",nowT,c,"BOS ↑",GREEN,9);
         SetTrend(prefix+"BOS_BULL",lht,lh,nowT,lh,GREEN,STYLE_DOT,2,false);
      }
      else if(ll>0 && c<ll)
      {
         SetText(prefix+"BOS_BEAR_TXT",nowT,c,"BOS ↓",RED,9);
         SetTrend(prefix+"BOS_BEAR",llt,ll,nowT,ll,RED,STYLE_DOT,2,false);
      }
   }
}

void DrawForecastMap(const Analysis &a)
{
   string base=prefix+"FORECAST_";
   ObjectDelete(0,base+"LABEL");
   ObjectDelete(0,base+"ZONE");
   ObjectDelete(0,base+"PATH");
   ObjectDelete(0,base+"ZONE_TOP");
   ObjectDelete(0,base+"ZONE_BOTTOM");

   if(!Use15MinForecast || a.forecastDirection=="NEUTRAL" || a.entry<=0) return;

   color c=(a.forecastDirection=="BULLISH"?GREEN:RED);
   int opacity=MathMax(0,MathMin(255,ForecastZoneOpacity));
   color zoneColor=(color)ColorToARGB(c,(uchar)opacity);

   datetime t0=TimeCurrent();
   datetime t1=t0+ForecastMinutes*60;
   double p1=a.entry;
   double move=MathMax(a.atr*0.60,MathAbs(a.tp1-a.entry)*0.35);
   double p2=(a.forecastDirection=="BULLISH"?p1+move:p1-move);
   double buffer=MathMax(a.atr*ForecastZoneATRBuffer,_Point*20.0);
   double zoneTop=MathMax(p1,p2)+buffer;
   double zoneBottom=MathMin(p1,p2)-buffer;

   // The whole forecast window is softly shaded: green for BUY forecast,
   // red for SELL forecast. It extends for exactly ForecastMinutes.
   string zone=base+"ZONE";
   if(ObjectCreate(0,zone,OBJ_RECTANGLE,0,t0,zoneTop,t1,zoneBottom))
   {
      ObjectSetInteger(0,zone,OBJPROP_COLOR,zoneColor);
      ObjectSetInteger(0,zone,OBJPROP_FILL,true);
      ObjectSetInteger(0,zone,OBJPROP_BACK,true);
      ObjectSetInteger(0,zone,OBJPROP_STYLE,STYLE_SOLID);
      ObjectSetInteger(0,zone,OBJPROP_WIDTH,1);
      ObjectSetInteger(0,zone,OBJPROP_SELECTABLE,false);
      ObjectSetInteger(0,zone,OBJPROP_SELECTED,false);
      ObjectSetInteger(0,zone,OBJPROP_HIDDEN,true);
      ObjectSetInteger(0,zone,OBJPROP_ZORDER,0);
   }

   // Thin boundaries make the forecast zone easy to read without overpowering candles.
   SetTrend(base+"ZONE_TOP",t0,zoneTop,t1,zoneTop,c,STYLE_DOT,1,false);
   SetTrend(base+"ZONE_BOTTOM",t0,zoneBottom,t1,zoneBottom,c,STYLE_DOT,1,false);

   string label=a.forecastDirection+" 15M "+(a.forecastDirection=="BULLISH"?"BUY ZONE":"SELL ZONE")+" "+IntegerToString(a.forecastConfidence)+"/100";
   SetText(base+"LABEL",t1,p2,label,c,10);

   if(ObjectCreate(0,base+"PATH",OBJ_TREND,0,t0,p1,t1,p2))
   {
      ObjectSetInteger(0,base+"PATH",OBJPROP_COLOR,c);
      ObjectSetInteger(0,base+"PATH",OBJPROP_WIDTH,3);
      ObjectSetInteger(0,base+"PATH",OBJPROP_STYLE,STYLE_SOLID);
      ObjectSetInteger(0,base+"PATH",OBJPROP_RAY_RIGHT,false);
      ObjectSetInteger(0,base+"PATH",OBJPROP_SELECTABLE,false);
      ObjectSetInteger(0,base+"PATH",OBJPROP_BACK,false);
   }
}

void DrawEntryMap(const Analysis &a)
{
   if(!ShowEntryMap) return;
   string et=prefix+"ENTRY_TEXT";
   if(a.entry<=0){ObjectDelete(0,et);return;}
   color c=(a.state==STATE_BUY?GREEN:(a.state==STATE_SELL?RED:WHITE));
   string label=(a.state==STATE_BUY?"BUY ENTRY":(a.state==STATE_SELL?"SELL ENTRY":(a.bias=="BULLISH"?"BUY WATCH":"SELL WATCH")));
   SetText(et,iTime(_Symbol,SignalTF,0),a.entry,label+"  "+DoubleToString(a.entry,_Digits),c,9);
   HLine(prefix+"LIVE_ENTRY",a.entry,c,STYLE_SOLID);
   if(a.sl>0) HLine(prefix+"LIVE_SL",a.sl,RED,STYLE_DASH);
   if(a.tp1>0) HLine(prefix+"LIVE_TP1",a.tp1,GREEN,STYLE_DASH);
   if(a.tp2>0) HLine(prefix+"LIVE_TP2",a.tp2,GREEN,STYLE_DOT);
}


void DrawClearTradeMap(const Analysis &a)
{
   string e=prefix+"CLEAR_ENTRY";
   string s=prefix+"CLEAR_SL";
   string t1=prefix+"CLEAR_TP1";
   string t2=prefix+"CLEAR_TP2";
   ObjectDelete(0,e); ObjectDelete(0,s); ObjectDelete(0,t1); ObjectDelete(0,t2);
   if(a.entry<=0) return;

   datetime now=iTime(_Symbol,SignalTF,0);
   bool buy=(a.state==STATE_BUY || (a.state==STATE_WAIT && a.bias=="BULLISH"));
   bool sell=(a.state==STATE_SELL || (a.state==STATE_WAIT && a.bias=="BEARISH"));
   color c=buy?GREEN:(sell?RED:YELLOW);
   string side=(a.state==STATE_BUY?(a.strength>=TradeReadyStrength?"BUY CONFIRMED":"BUY DETECTED"):
                a.state==STATE_SELL?(a.strength>=TradeReadyStrength?"SELL CONFIRMED":"SELL DETECTED"):
                buy?"BUY WATCH":"SELL WATCH");

   SetText(e,now,a.entry,side+" | ENTRY "+DoubleToString(a.entry,_Digits),c,11);
   if(a.sl>0) SetText(s,now,a.sl,"SL  "+DoubleToString(a.sl,_Digits),RED,9);
   if(a.tp1>0) SetText(t1,now,a.tp1,"TP1 "+DoubleToString(a.tp1,_Digits),GREEN,9);
   if(a.tp2>0) SetText(t2,now,a.tp2,"TP2 "+DoubleToString(a.tp2,_Digits),GREEN,9);
}


struct FlowPoint
{
   datetime t;
   double p;
   int type; // 1 liquidity, 2 BOS, 3 zone, 4 entry
};

bool RecentLiquiditySweep(FlowPoint &fp,bool &bullish)
{
   fp.t=0; fp.p=0; fp.type=1; bullish=false;
   int scan=MathMax(8,MathMin(FlowScanBars,60));
   for(int i=1;i<=scan;i++)
   {
      double hi=iHigh(_Symbol,SignalTF,i), lo=iLow(_Symbol,SignalTF,i), cl=iClose(_Symbol,SignalTF,i);
      if(hi<=0||lo<=0||cl<=0) continue;
      double prevHigh=-DBL_MAX, prevLow=DBL_MAX;
      int span=MathMin(12,scan-i+1);
      for(int j=i+1;j<=i+span;j++)
      {
         prevHigh=MathMax(prevHigh,iHigh(_Symbol,SignalTF,j));
         prevLow=MathMin(prevLow,iLow(_Symbol,SignalTF,j));
      }
      if(prevLow>0 && lo<prevLow && cl>prevLow)
      {
         fp.t=iTime(_Symbol,SignalTF,i); fp.p=lo; bullish=true; return true;
      }
      if(prevHigh>-DBL_MAX/2 && hi>prevHigh && cl<prevHigh)
      {
         fp.t=iTime(_Symbol,SignalTF,i); fp.p=hi; bullish=false; return true;
      }
   }
   return false;
}

bool RecentBOS(FlowPoint &fp,bool bullish)
{
   fp.t=0; fp.p=0; fp.type=2;
   double h=0,l=0; datetime ht=0,lt=0;
   double ph=0,pl=0; datetime pht=0,plt=0;
   if(!FindRecentFractals(h,ph,ht,pht,l,pl,lt,plt)) return false;
   int scan=MathMax(1,MathMin(FlowScanBars,24));
   for(int i=1;i<=scan;i++)
   {
      double c=iClose(_Symbol,SignalTF,i);
      if(c<=0) continue;
      if(bullish && h>0 && c>h)
      {
         fp.t=iTime(_Symbol,SignalTF,i); fp.p=h; return true;
      }
      if(!bullish && l>0 && c<l)
      {
         fp.t=iTime(_Symbol,SignalTF,i); fp.p=l; return true;
      }
   }
   return false;
}

bool RecentFVGPoint(FlowPoint &fp,bool bullish)
{
   fp.t=0; fp.p=0; fp.type=3;
   double atr=Buf(hATR,0,1); if(atr==EMPTY_VALUE||atr<=0) return false;
   int scan=MathMax(1,MathMin(FlowScanBars,30));
   for(int i=1;i<=scan;i++)
   {
      double hOld=iHigh(_Symbol,SignalTF,i+2),lOld=iLow(_Symbol,SignalTF,i+2);
      double hNew=iHigh(_Symbol,SignalTF,i),lNew=iLow(_Symbol,SignalTF,i);
      if(bullish && lNew>hOld && (lNew-hOld)>=atr*0.10)
      { fp.t=iTime(_Symbol,SignalTF,i); fp.p=(hOld+lNew)*0.5; return true; }
      if(!bullish && hNew<lOld && (lOld-hNew)>=atr*0.10)
      { fp.t=iTime(_Symbol,SignalTF,i); fp.p=(hNew+lOld)*0.5; return true; }
   }
   return false;
}

bool RecentOBPoint(FlowPoint &fp,bool bullish)
{
   fp.t=0; fp.p=0; fp.type=3;
   double atr=Buf(hATR,0,1); if(atr==EMPTY_VALUE||atr<=0) return false;
   int scan=MathMax(2,MathMin(FlowScanBars,20));
   for(int i=1;i<=scan;i++)
   {
      double o=iOpen(_Symbol,SignalTF,i), c=iClose(_Symbol,SignalTF,i);
      double oPrev=iOpen(_Symbol,SignalTF,i+1), cPrev=iClose(_Symbol,SignalTF,i+1);
      if(bullish && c>o && c-o>=atr*0.55 && cPrev<oPrev)
      { fp.t=iTime(_Symbol,SignalTF,i+1); fp.p=(oPrev+cPrev)*0.5; return true; }
      if(!bullish && c<o && o-c>=atr*0.55 && cPrev>oPrev)
      { fp.t=iTime(_Symbol,SignalTF,i+1); fp.p=(oPrev+cPrev)*0.5; return true; }
   }
   return false;
}

void FlowLabel(const string name,datetime t,double p,const string txt,color c)
{
   if(!ShowFlowLabels) return;
   SetText(name,t,p,txt,c,8);
}

void DrawFlowSequence(const Analysis &a)
{
   if(!ShowFlowSequence) return;
   string base=prefix+"FLOW_";
   // Clear only the flow-sequence objects; keep the main map intact.
   for(int i=0;i<10;i++)
   {
      ObjectDelete(0,base+"L"+IntegerToString(i));
      ObjectDelete(0,base+"T"+IntegerToString(i));
      ObjectDelete(0,base+"A"+IntegerToString(i));
   }

   bool bull=(a.bias=="BULLISH" || (a.state==STATE_BUY));
   bool bear=(a.bias=="BEARISH" || (a.state==STATE_SELL));
   if(!bull && !bear) return;
   bool directionBull=bull && !bear;
   if(bull && bear) directionBull=(a.buyScore>=a.sellScore);
   color c=directionBull?GREEN:RED;

   FlowPoint liq,bos,zone; bool sweepBull=false;
   bool hasLiq=RecentLiquiditySweep(liq,sweepBull);
   if(hasLiq && sweepBull!=directionBull) hasLiq=false;
   bool hasBos=RecentBOS(bos,directionBull);
   bool hasZone=RecentFVGPoint(zone,directionBull);
   if(!hasZone) hasZone=RecentOBPoint(zone,directionBull);

   int n=0;
   if(hasLiq)
   {
      SetChartArrow(base+"A"+IntegerToString(n),liq.t,liq.p,directionBull,c);
      FlowLabel(base+"T"+IntegerToString(n),liq.t,liq.p+(directionBull?-a.atr*0.5:a.atr*0.5),"1  LIQUIDITY SWEEP",c);
      n++;
   }
   if(hasBos)
   {
      SetChartArrow(base+"A"+IntegerToString(n),bos.t,bos.p,directionBull,c);
      FlowLabel(base+"T"+IntegerToString(n),bos.t,bos.p+(directionBull?a.atr*0.35:-a.atr*0.35),directionBull?"2  BOS ↑":"2  BOS ↓",c);
      n++;
   }
   if(hasZone)
   {
      SetText(base+"A"+IntegerToString(n),zone.t,zone.p,"3",c,11);
      FlowLabel(base+"T"+IntegerToString(n),zone.t,zone.p+(directionBull?-a.atr*0.35:a.atr*0.35),"3  FVG / OB",c);
      n++;
   }

   datetime now=iTime(_Symbol,SignalTF,0); double ep=a.entry>0?a.entry:PriceNow(directionBull);
   if(now>0&&ep>0)
   {
      SetChartArrow(base+"A"+IntegerToString(n),now,ep,directionBull,c);
      FlowLabel(base+"T"+IntegerToString(n),now,ep+(directionBull?-a.atr*0.35:a.atr*0.35),directionBull?"4  BUY ENTRY":"4  SELL ENTRY",c);
      n++;
   }

   // Connect the actual detected points in chronological order where available.
   FlowPoint pts[4]; int pc=0;
   if(hasLiq) pts[pc++]=liq;
   if(hasBos) pts[pc++]=bos;
   if(hasZone) pts[pc++]=zone;
   if(now>0&&ep>0){pts[pc].t=now;pts[pc].p=ep;pts[pc].type=4;pc++;}
   for(int i=0;i<pc-1;i++)
   {
      datetime t1=pts[i].t,t2=pts[i+1].t; double p1=pts[i].p,p2=pts[i+1].p;
      if(t1>0&&t2>0&&t1!=t2) SetTrend(base+"L"+IntegerToString(i),t1,p1,t2,p2,c,STYLE_SOLID,2,false);
   }

   SetLabel(prefix+"FLOW_STATUS","FLOW: "+(directionBull?"BULLISH":"BEARISH")+"  |  "+IntegerToString(n)+"/4 stages",PanelX+16,PanelY+540,c,8);
}

void DrawLiveIntelligence(const Analysis &a)
{
   DrawStructureAndLiquidity(a);
   DrawOrderBlockMap(a);
   DrawEntryMap(a);
   DrawForecastMap(a);
   DrawClearTradeMap(a);
   DrawFlowSequence(a);
}

void DrawLevels(const Analysis &a)
{
   DrawFVGZone();
   if(DrawSupportResistance){HLine(prefix+"SUP",a.lv.support,GREEN);HLine(prefix+"RES",a.lv.resistance,RED);}

   // Keep the visual trade map available while a directional setup is forming,
   // not only after the state reaches confirmed BUY/SELL.
   bool directional=(a.bias=="BULLISH" || a.bias=="BEARISH" || a.state==STATE_BUY || a.state==STATE_SELL);
   if(directional && a.entry>0)
   {
      color ec=(a.state==STATE_BUY||a.bias=="BULLISH")?GREEN:(a.state==STATE_SELL||a.bias=="BEARISH")?RED:YELLOW;
      HLine(prefix+"ENTRY",a.entry,ec,STYLE_SOLID);
      if(a.sl>0)HLine(prefix+"SL",a.sl,RED,STYLE_DASH);
      if(a.tp1>0)HLine(prefix+"TP1",a.tp1,GREEN,STYLE_DASH);
      if(a.tp2>0)HLine(prefix+"TP2",a.tp2,GREEN,STYLE_DOT);
   }
   else
   {
      ObjectDelete(0,prefix+"ENTRY"); ObjectDelete(0,prefix+"SL"); ObjectDelete(0,prefix+"TP1"); ObjectDelete(0,prefix+"TP2");
   }
}


void DrawArrow(const Analysis &a)
{
   if(!DrawSignalArrows || (a.state!=STATE_BUY && a.state!=STATE_SELL))return;
   string n=prefix+(a.state==STATE_BUY?"BUY_ARROW":"SELL_ARROW");datetime t=iTime(_Symbol,SignalTF,1);double p=(a.state==STATE_BUY?iLow(_Symbol,SignalTF,1)-a.atr*0.25:iHigh(_Symbol,SignalTF,1)+a.atr*0.25);
   if(ObjectFind(0,n)<0)ObjectCreate(0,n,a.state==STATE_BUY?OBJ_ARROW_BUY:OBJ_ARROW_SELL,0,t,p);else ObjectMove(0,n,0,t,p);
   ObjectSetInteger(0,n,OBJPROP_COLOR,a.state==STATE_BUY?GREEN:RED);ObjectSetInteger(0,n,OBJPROP_WIDTH,3);
}

void AlertForState(const Analysis &a)
{
   if(!EnableAlerts)return;
   if((a.state==STATE_BUY || a.state==STATE_SELL) && !a.marginOK) return;
   datetime bar=iTime(_Symbol,SignalTF,1);string key=(a.state==STATE_BUY?"BUY":(a.state==STATE_SELL?"SELL":"WAIT"));
   if(a.state==STATE_WAIT && !EnableEarlyWarning)return;
   if(key==lastAlertKey && bar==lastAlertBar && (TimeCurrent()-lastAlertTime)<AlertCooldownSeconds)return;
   if(a.state==STATE_WAIT && a.strength<55)return;
   lastAlertKey=key;lastAlertBar=bar;lastAlertTime=TimeCurrent();
   string msg="V4.12.3 "+assetName+" "+key+" | Strength "+IntegerToString(a.strength)+"/100";
   if(a.state==STATE_BUY||a.state==STATE_SELL)msg+=" | Entry "+DoubleToString(a.entry,_Digits)+" SL "+DoubleToString(a.sl,_Digits)+" TP1 "+DoubleToString(a.tp1,_Digits)+" TP2 "+DoubleToString(a.tp2,_Digits);
   else msg+=" | "+a.reason;
   if(!a.guardianOK) msg+=" | GUARDIAN ACTIVE";
   if(EnableSoundAlerts)PlaySound(a.state==STATE_BUY?BuySound:(a.state==STATE_SELL?SellSound:WaitSound));
   Alert(msg);
   if(EnablePushAlerts && TerminalInfoInteger(TERMINAL_NOTIFICATIONS_ENABLED))SendNotification(msg);
}

int OpenPositions()
{
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;i--){ulong ticket=PositionGetTicket(i);if(ticket>0&&PositionGetString(POSITION_SYMBOL)==_Symbol&&(ulong)PositionGetInteger(POSITION_MAGIC)==MagicNumber)n++;}
   return n;
}

double NormalizeLot(double lot)
{
   double minv=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN),maxv=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX),step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);if(step<=0)step=minv;
   lot=MathMax(minv,MathMin(maxv,lot));return NormalizeDouble(MathFloor(lot/step)*step,2);
}

double RiskLot(double entry,double sl)
{
   if(!UseRiskPercent)return NormalizeLot(FixedLot);
   double money=AccountInfoDouble(ACCOUNT_BALANCE)*RiskPercent/100.0;
   double dist=MathAbs(entry-sl);
   if(money<=0.0 || dist<=0.0 || entry<=0.0 || sl<=0.0) return NormalizeLot(FixedLot);
   ENUM_ORDER_TYPE typ=(entry>sl?ORDER_TYPE_BUY:ORDER_TYPE_SELL);
   double lossOneLot=0.0;
   if(OrderCalcProfit(typ,_Symbol,1.0,entry,sl,lossOneLot) && MathAbs(lossOneLot)>0.0)
      return NormalizeLot(money/MathAbs(lossOneLot));
   double tv=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double ts=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tv<=0.0 || ts<=0.0) return NormalizeLot(FixedLot);
   return NormalizeLot(money/((dist/ts)*tv));
}

double MarginLotForOrder(ENUM_ORDER_TYPE orderType,double entry,double desiredLot,double &requiredMargin,double &projectedLevel)
{
   requiredMargin=0.0; projectedLevel=0.0;
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   double used=AccountInfoDouble(ACCOUNT_MARGIN);
   double free=AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   if(equity<=0.0 || free<=0.0 || desiredLot<=0.0) return 0.0;

   double minv=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(step<=0.0) step=minv;
   double maxv=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double lot=MathMin(desiredLot,maxv);

   double marginPerLot=0.0;
   if(!OrderCalcMargin(orderType,_Symbol,1.0,entry,marginPerLot) || marginPerLot<=0.0)
      return 0.0;

   double maxByFree=(free*(MaxMarginUsePercent/100.0))/marginPerLot;
   double maxByLevel=desiredLot;
   if(MinProjectedMarginLevel>0.0)
   {
      double maxTotalMargin=equity/(MinProjectedMarginLevel/100.0);
      double availableForTrade=maxTotalMargin-used;
      maxByLevel=availableForTrade/marginPerLot;
   }
   lot=MathMin(lot,MathMin(maxByFree,maxByLevel));
   lot=MathFloor(lot/step)*step;
   if(lot<minv) return 0.0;
   lot=MathMin(maxv,lot);
   lot=NormalizeLot(lot);

   if(!OrderCalcMargin(orderType,_Symbol,lot,entry,requiredMargin) || requiredMargin<=0.0) return 0.0;
   double projected=used+requiredMargin;
   projectedLevel=(projected>0.0)?(equity/projected*100.0):999999.0;
   if(requiredMargin>free*(MaxMarginUsePercent/100.0)) return 0.0;
   if(MinProjectedMarginLevel>0.0 && projectedLevel<MinProjectedMarginLevel) return 0.0;
   return lot;
}

double MarginAwareLot(const Analysis &a)
{
   double baseLot=RiskLot(a.entry,a.sl);
   if(!UseMarginGuard) return baseLot;
   ENUM_ORDER_TYPE typ=(a.state==STATE_BUY?ORDER_TYPE_BUY:ORDER_TYPE_SELL);
   double req=0.0,proj=0.0;
   return MarginLotForOrder(typ,a.entry,baseLot,req,proj);
}

void UpdateMarginInfo(Analysis &a)
{
   a.balance=AccountInfoDouble(ACCOUNT_BALANCE);
   a.equity=AccountInfoDouble(ACCOUNT_EQUITY);
   a.marginUsed=AccountInfoDouble(ACCOUNT_MARGIN);
   a.freeMargin=AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   a.marginLevel=AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   a.tradeMargin=0.0; a.projectedMarginLevel=a.marginLevel; a.lot=0.0; a.marginOK=true;
   if(a.state==STATE_WAIT || a.entry<=0.0 || a.sl<=0.0) return;
   a.lot=MarginAwareLot(a);
   ENUM_ORDER_TYPE typ=(a.state==STATE_BUY?ORDER_TYPE_BUY:ORDER_TYPE_SELL);
   if(a.lot<=0.0){a.marginOK=false; return;}
   if(!OrderCalcMargin(typ,_Symbol,a.lot,a.entry,a.tradeMargin)){a.marginOK=false;return;}
   double projected=a.marginUsed+a.tradeMargin;
   a.projectedMarginLevel=(projected>0.0)?(a.equity/projected*100.0):999999.0;
   a.marginOK=(a.tradeMargin<=a.freeMargin*(MaxMarginUsePercent/100.0) && (MinProjectedMarginLevel<=0.0 || a.projectedMarginLevel>=MinProjectedMarginLevel));
   if(!a.marginOK){a.lot=0.0;}
   if(!a.guardianOK) a.reason=a.guardianReason;
   else if(!a.marginOK) a.reason="SIGNAL DETECTED: margin guard would block execution at current size";
   else a.reason=BuildDecisionReason(a);
   CalculateReadiness(a);
}


string GuardianKey()
{
   return StringFormat("ALT_GUARD_PEAK_%I64d_%I64u",AccountInfoInteger(ACCOUNT_LOGIN),MagicNumber);
}

datetime StartOfDay(datetime t)
{
   MqlDateTime d; TimeToStruct(t,d); d.hour=0; d.min=0; d.sec=0; return StructToTime(d);
}

void GetGuardianStats(double &startBalance,double &realized,double &lossMoney,double &lossPct,int &trades,int &losses,int &cooldown)
{
   startBalance=AccountInfoDouble(ACCOUNT_BALANCE); realized=0; trades=0; losses=0; cooldown=0;
   datetime now=TimeTradeServer(); if(now<=0) now=TimeCurrent();
   datetime day=StartOfDay(now);
   if(HistorySelect(day,now))
   {
      int total=HistoryDealsTotal();
      datetime lastLoss=0;
      for(int i=0;i<total;i++)
      {
         ulong ticket=HistoryDealGetTicket(i); if(ticket==0) continue;
         long entry=HistoryDealGetInteger(ticket,DEAL_ENTRY);
         if(entry!=DEAL_ENTRY_OUT && entry!=DEAL_ENTRY_OUT_BY) continue;
         long magic=HistoryDealGetInteger(ticket,DEAL_MAGIC);
         if(!GuardianAccountWide && (ulong)magic!=MagicNumber) continue;
         double p=HistoryDealGetDouble(ticket,DEAL_PROFIT)+HistoryDealGetDouble(ticket,DEAL_SWAP)+HistoryDealGetDouble(ticket,DEAL_COMMISSION);
         realized+=p; trades++;
         if(p<0){losses++; datetime dt=(datetime)HistoryDealGetInteger(ticket,DEAL_TIME); if(dt>lastLoss) lastLoss=dt;}
      }
      startBalance=AccountInfoDouble(ACCOUNT_BALANCE)-realized;
      if(LossCooldownMinutes>0 && lastLoss>0)
      {
         int elapsed=(int)(now-lastLoss); int wait=LossCooldownMinutes*60-elapsed;
         cooldown=(wait>0)?(int)MathCeil((double)wait/60.0):0;
      }
   }
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   lossMoney=MathMax(0.0,startBalance-equity);
   lossPct=(startBalance>0)?(lossMoney/startBalance*100.0):0.0;
}

double UpdatePeakEquity()
{
   string key=GuardianKey(); double peak=AccountInfoDouble(ACCOUNT_EQUITY);
   if(GlobalVariableCheck(key)) peak=MathMax(peak,GlobalVariableGet(key));
   GlobalVariableSet(key,peak); return peak;
}

void GuardianEmergencyClose()
{
   if(!EmergencyCloseEAOrders) return;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong ticket=PositionGetTicket(i); if(ticket==0) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC)!=MagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      trade.SetExpertMagicNumber(MagicNumber); trade.PositionClose(ticket);
   }
}

void UpdateGuardian(Analysis &a)
{
   a.guardianOK=true; a.guardianReason="GUARDIAN OK";
   a.dailyStartBalance=0; a.dailyRealizedPL=0; a.dailyLossMoney=0; a.dailyLossPct=0;
   a.peakEquity=UpdatePeakEquity();
   a.drawdownPct=(a.peakEquity>0)?MathMax(0.0,(a.peakEquity-a.equity)/a.peakEquity*100.0):0;
   a.tradesToday=0; a.losingTradesToday=0; a.lossCooldownMinutes=0;
   if(!UseTradingGuardian) return;
   GetGuardianStats(a.dailyStartBalance,a.dailyRealizedPL,a.dailyLossMoney,a.dailyLossPct,a.tradesToday,a.losingTradesToday,a.lossCooldownMinutes);
   double maxLoss=MaxDailyLossMoney>0?MaxDailyLossMoney:(a.dailyStartBalance*MaxDailyLossPercent/100.0);
   if(maxLoss>0 && a.dailyLossMoney>=maxLoss){a.guardianOK=false;a.guardianReason="DAILY LOSS LIMIT";}
   if(a.drawdownPct>=MaxEquityDrawdownPercent && MaxEquityDrawdownPercent>0){a.guardianOK=false;a.guardianReason="EQUITY DRAWDOWN LIMIT";}
   if(MaxTradesPerDay>0 && a.tradesToday>=MaxTradesPerDay){a.guardianOK=false;a.guardianReason="DAILY TRADE LIMIT";}
   if(MaxLosingTradesPerDay>0 && a.losingTradesToday>=MaxLosingTradesPerDay){a.guardianOK=false;a.guardianReason="LOSS COUNT LIMIT";}
   if(a.lossCooldownMinutes>0){a.guardianOK=false;a.guardianReason="LOSS COOLDOWN "+IntegerToString(a.lossCooldownMinutes)+"m";}
   if(!a.guardianOK) GuardianEmergencyClose();
   a.reason=BuildDecisionReason(a);
   CalculateReadiness(a);
}

void ExecuteTrade(const Analysis &a)
{
   if(!AllowAlgoTrading||a.state==STATE_WAIT||a.newsBlocked||!a.spreadOK||!a.marginOK||!a.guardianOK||OpenPositions()>=MaxOpenTrades)return;
   double lot=a.lot;
   if(lot<=0.0)return;trade.SetExpertMagicNumber(MagicNumber);trade.SetDeviationInPoints(20);
   bool ok=false;
   if(a.state==STATE_BUY)ok=trade.Buy(lot,_Symbol,0,a.sl,a.tp2,"ALT V4.12.3 BUY");
   if(a.state==STATE_SELL)ok=trade.Sell(lot,_Symbol,0,a.sl,a.tp2,"ALT V4.12.3 SELL");
   if(!ok)Print("V4.12.3 trade failed: ",trade.ResultRetcode()," ",trade.ResultRetcodeDescription());
}

void EvaluateClosedBar()
{
   Analysis a;CalculateSignal(a);UpdateMarginInfo(a);UpdateGuardian(a);DrawLevels(a);DrawArrow(a);DrawLiveIntelligence(a);DrawPanel(a);AlertForState(a);ExecuteTrade(a);ChartRedraw();
}

void UpdateLivePanel()
{
   Analysis a;CalculateSignal(a);UpdateMarginInfo(a);UpdateGuardian(a);
   DrawLevels(a);DrawArrow(a);DrawLiveIntelligence(a);
   if(ShowDashboard)DrawPanel(a);
   ChartRedraw();
}

int OnInit()
{
   ApplyAssetProfile();
   hFast=iMA(_Symbol,SignalTF,FastEMA,0,MODE_EMA,PRICE_CLOSE);
   hSlow=iMA(_Symbol,SignalTF,SlowEMA,0,MODE_EMA,PRICE_CLOSE);
   hRSI=iRSI(_Symbol,SignalTF,RSIPeriod,PRICE_CLOSE);
   hATR=iATR(_Symbol,SignalTF,ATRPeriod);
   hADX=iADXWilder(_Symbol,SignalTF,ADXPeriod);
   hFractals=iFractals(_Symbol,SignalTF);
   hFastHTF=iMA(_Symbol,ConfirmTF,FastEMA,0,MODE_EMA,PRICE_CLOSE);
   hSlowHTF=iMA(_Symbol,ConfirmTF,SlowEMA,0,MODE_EMA,PRICE_CLOSE);
   hRSIHTF=iRSI(_Symbol,ConfirmTF,RSIPeriod,PRICE_CLOSE);
   hADXHTF=iADXWilder(_Symbol,ConfirmTF,ADXPeriod);
   if(hFast==INVALID_HANDLE||hSlow==INVALID_HANDLE||hRSI==INVALID_HANDLE||hATR==INVALID_HANDLE||hADX==INVALID_HANDLE||hFractals==INVALID_HANDLE||hFastHTF==INVALID_HANDLE||hSlowHTF==INVALID_HANDLE||hRSIHTF==INVALID_HANDLE||hADXHTF==INVALID_HANDLE)return INIT_FAILED;
   DeleteObjects();
   EventSetTimer(1);
   lastSignalBar=iTime(_Symbol,SignalTF,0);
   EvaluateClosedBar();
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();DeleteObjects();
   if(hFast!=INVALID_HANDLE)IndicatorRelease(hFast);if(hSlow!=INVALID_HANDLE)IndicatorRelease(hSlow);if(hRSI!=INVALID_HANDLE)IndicatorRelease(hRSI);if(hATR!=INVALID_HANDLE)IndicatorRelease(hATR);if(hADX!=INVALID_HANDLE)IndicatorRelease(hADX);if(hFractals!=INVALID_HANDLE)IndicatorRelease(hFractals);if(hFastHTF!=INVALID_HANDLE)IndicatorRelease(hFastHTF);if(hSlowHTF!=INVALID_HANDLE)IndicatorRelease(hSlowHTF);if(hRSIHTF!=INVALID_HANDLE)IndicatorRelease(hRSIHTF);if(hADXHTF!=INVALID_HANDLE)IndicatorRelease(hADXHTF);
}

void OnTick()
{
   datetime bar=iTime(_Symbol,SignalTF,0);
   if(bar!=lastSignalBar){lastSignalBar=bar;EvaluateClosedBar();}
   else UpdateLivePanel();
}

void OnTimer(){UpdateLivePanel();}