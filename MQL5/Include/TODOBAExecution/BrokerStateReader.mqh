#ifndef TODOBA_BROKER_STATE_READER_MQH
#define TODOBA_BROKER_STATE_READER_MQH

#include <TODOBAExecution/AccountFingerprint.mqh>
#include <TODOBAExecution/SymbolMapper.mqh>


struct TODOBABrokerState
{
   string account_fingerprint;

   double equity;
   int open_position_count;

   string symbol;

   double bid;
   double ask;
   double spread_points;
};


class TODOBABrokerStateReader
{
public:

   static bool Read(
      string symbol,
      TODOBABrokerState &state
   )
   {
      string account_fingerprint =
         TODOBAAccountFingerprint::Build();

      if(StringLen(account_fingerprint) == 0)
         return false;

      double equity = AccountInfoDouble(
         ACCOUNT_EQUITY
      );

      if(equity <= 0.0)
         return false;

      symbol = TODOBA_SymbolMapper::Resolve(
         symbol
      );

      if(StringLen(symbol) == 0)
         return false;

      if(!SymbolSelect(
         symbol,
         true
      ))
         return false;

      MqlTick tick;

      if(!SymbolInfoTick(
         symbol,
         tick
      ))
         return false;

      if(
         tick.bid <= 0.0
         ||
         tick.ask <= 0.0
      )
         return false;

      double point = SymbolInfoDouble(
         symbol,
         SYMBOL_POINT
      );

      if(point <= 0.0)
         return false;

      int open_position_count = 0;

      int total_positions = PositionsTotal();

      for(
         int index = 0;
         index < total_positions;
         index++
      )
      {
         string position_symbol =
            PositionGetSymbol(
               index
            );

         if(
            position_symbol
            == symbol
         )
         {
            open_position_count++;
         }
      }

      state.account_fingerprint =
         account_fingerprint;

      state.equity = equity;

      state.open_position_count =
         open_position_count;

      state.symbol = symbol;

      state.bid = tick.bid;

      state.ask = tick.ask;

      state.spread_points = (
         tick.ask - tick.bid
      ) / point;

      return true;
   }
};


#endif