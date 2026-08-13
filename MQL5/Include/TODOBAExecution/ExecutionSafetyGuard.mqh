#ifndef TODOBA_EXECUTION_SAFETY_GUARD_MQH
#define TODOBA_EXECUTION_SAFETY_GUARD_MQH

#include <TODOBAExecution/SymbolMapper.mqh>


class TODOBAExecutionSafetyGuard
{
public:

   static bool Allow(
      string symbol,
      const double max_spread_points,
      const int max_open_trades,
      string &reason
   )
   {
      reason = "";

      if(max_spread_points <= 0.0)
      {
         reason =
            "Maximum spread points must be greater than zero.";

         return false;
      }

      if(max_open_trades <= 0)
      {
         reason =
            "Maximum open trades must be greater than zero.";

         return false;
      }

      symbol = TODOBA_SymbolMapper::Resolve(
         symbol
      );

      if(StringLen(symbol) == 0)
      {
         reason =
            "Broker symbol could not be resolved.";

         return false;
      }

      if(!SymbolSelect(
         symbol,
         true
      ))
      {
         reason =
            "Broker symbol could not be selected.";

         return false;
      }

      MqlTick tick;

      if(!SymbolInfoTick(
         symbol,
         tick
      ))
      {
         reason =
            "Broker tick data is unavailable.";

         return false;
      }

      if(
         tick.bid <= 0.0
         ||
         tick.ask <= 0.0
      )
      {
         reason =
            "Market is closed.";

         return false;
      }

      double point = SymbolInfoDouble(
         symbol,
         SYMBOL_POINT
      );

      if(point <= 0.0)
      {
         reason =
            "Broker symbol point is invalid.";

         return false;
      }

      double spread_points = (
         tick.ask - tick.bid
      ) / point;

      if(
         spread_points
         > max_spread_points
      )
      {
         reason =
            "Spread too large.";

         return false;
      }

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

      if(
         open_position_count
         >= max_open_trades
      )
      {
         reason =
            "Maximum open trade limit reached.";

         return false;
      }

      reason = "Approved.";

      return true;
   }
};


#endif