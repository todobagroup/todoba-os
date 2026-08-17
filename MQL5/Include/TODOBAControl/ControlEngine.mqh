#ifndef TODOBA_CONTROL_ENGINE_MQH
#define TODOBA_CONTROL_ENGINE_MQH


#include <Trade/Trade.mqh>

#include <TODOBAControl/ControlMissionParser.mqh>
#include <TODOBAControl/ControlResult.mqh>

#include <TODOBAExecution/SymbolMapper.mqh>


class TODOBAControlEngine
{
private:

   CTrade trade;


   static TODOBAControlResult NewResult()
   {
      TODOBAControlResult result;

      result.success = true;

      result.matched_position_count = 0;
      result.closed_position_count = 0;

      result.matched_pending_order_count = 0;
      result.canceled_pending_order_count = 0;

      result.failed_item_count = 0;

      result.failure_reason = "";

      return result;
   }


   static void FailResult(
      TODOBAControlResult &result,
      const string reason
   )
   {
      result.success = false;

      if(
         StringLen(
            result.failure_reason
         ) == 0
      )
      {
         result.failure_reason = reason;
      }
   }


   static void FailItem(
      TODOBAControlResult &result,
      const string reason
   )
   {
      result.failed_item_count++;

      FailResult(
         result,
         reason
      );
   }


   static bool IsHedgingAccount()
   {
      long margin_mode =
         AccountInfoInteger(
            ACCOUNT_MARGIN_MODE
         );

      return (
         margin_mode
         ==
         ACCOUNT_MARGIN_MODE_RETAIL_HEDGING
      );
   }


   static bool IsPositionAction(
      const string action
   )
   {
      return (
         action == "CLOSE_GREEN"
         ||
         action == "CLOSE_RED"
         ||
         action == "CLOSE_BUY"
         ||
         action == "CLOSE_SELL"
         ||
         action == "CLOSE_ALL_POSITIONS"
         ||
         action == "FLATTEN_ALL"
      );
   }


   static bool IsPendingAction(
      const string action
   )
   {
      return (
         action == "CANCEL_ALL_PENDING"
         ||
         action == "FLATTEN_ALL"
      );
   }


   static bool PositionMatchesAction(
      const string action
   )
   {
      if(
         action
         ==
         "CLOSE_ALL_POSITIONS"
      )
      {
         return true;
      }


      if(
         action
         ==
         "FLATTEN_ALL"
      )
      {
         return true;
      }


      double profit =
         PositionGetDouble(
            POSITION_PROFIT
         );


      if(
         action
         ==
         "CLOSE_GREEN"
      )
      {
         return profit > 0.0;
      }


      if(
         action
         ==
         "CLOSE_RED"
      )
      {
         return profit < 0.0;
      }


      long position_type =
         PositionGetInteger(
            POSITION_TYPE
         );


      if(
         action
         ==
         "CLOSE_BUY"
      )
      {
         return (
            position_type
            ==
            POSITION_TYPE_BUY
         );
      }


      if(
         action
         ==
         "CLOSE_SELL"
      )
      {
         return (
            position_type
            ==
            POSITION_TYPE_SELL
         );
      }


      return false;
   }


   bool CloseOwnedPositions(
      const TODOBAControlMission &mission,
      const string resolved_symbol,
      TODOBAControlResult &result
   )
   {
      int total_positions =
         PositionsTotal();


      for(
         int index =
            total_positions - 1;
         index >= 0;
         index--
      )
      {
         ulong ticket =
            PositionGetTicket(
               index
            );

         if(ticket == 0)
            continue;


         string position_symbol =
            PositionGetString(
               POSITION_SYMBOL
            );

         if(
            position_symbol
            != resolved_symbol
         )
         {
            continue;
         }


         long position_magic =
            PositionGetInteger(
               POSITION_MAGIC
            );

         if(
            position_magic
            != mission.magic_number
         )
         {
            continue;
         }


         if(
            !PositionMatchesAction(
               mission.action
            )
         )
         {
            continue;
         }


         result.matched_position_count++;


         bool request_ok =
            trade.PositionClose(
               ticket
            );

         uint retcode =
            trade.ResultRetcode();


         if(
            !request_ok
            ||
            retcode
            != TRADE_RETCODE_DONE
         )
         {
            FailItem(
               result,
               "Position close failed."
            );

            continue;
         }


         result.closed_position_count++;
      }


      return (
         result.failed_item_count
         == 0
      );
   }


   bool CancelOwnedPendingOrders(
      const TODOBAControlMission &mission,
      const string resolved_symbol,
      TODOBAControlResult &result
   )
   {
      int total_orders =
         OrdersTotal();


      for(
         int index =
            total_orders - 1;
         index >= 0;
         index--
      )
      {
         ulong ticket =
            OrderGetTicket(
               index
            );

         if(ticket == 0)
            continue;


         string order_symbol =
            OrderGetString(
               ORDER_SYMBOL
            );

         if(
            order_symbol
            != resolved_symbol
         )
         {
            continue;
         }


         long order_magic =
            OrderGetInteger(
               ORDER_MAGIC
            );

         if(
            order_magic
            != mission.magic_number
         )
         {
            continue;
         }


         result.matched_pending_order_count++;


         bool request_ok =
            trade.OrderDelete(
               ticket
            );

         uint retcode =
            trade.ResultRetcode();


         if(
            !request_ok
            ||
            retcode
            != TRADE_RETCODE_DONE
         )
         {
            FailItem(
               result,
               "Pending order cancel failed."
            );

            continue;
         }


         result.canceled_pending_order_count++;
      }


      return (
         result.failed_item_count
         == 0
      );
   }


public:

   TODOBAControlResult Execute(
      const TODOBAControlMission &mission
   )
   {
      TODOBAControlResult result =
         NewResult();


      if(
         !IsHedgingAccount()
      )
      {
         FailResult(
            result,
            "TODOBA Control requires HEDGING account."
         );

         return result;
      }


      if(
         mission.magic_number <= 0
      )
      {
         FailResult(
            result,
            "Invalid TODOBA magic number."
         );

         return result;
      }


      string resolved_symbol =
         TODOBA_SymbolMapper::Resolve(
            mission.symbol
         );


      if(
         StringLen(
            resolved_symbol
         ) == 0
      )
      {
         FailResult(
            result,
            "Unable to resolve control symbol."
         );

         return result;
      }


      if(
         !SymbolSelect(
            resolved_symbol,
            true
         )
      )
      {
         FailResult(
            result,
            "Unable to select control symbol."
         );

         return result;
      }


      trade.SetExpertMagicNumber(
         mission.magic_number
      );


      if(
         IsPositionAction(
            mission.action
         )
      )
      {
         CloseOwnedPositions(
            mission,
            resolved_symbol,
            result
         );
      }


      if(
         IsPendingAction(
            mission.action
         )
      )
      {
         CancelOwnedPendingOrders(
            mission,
            resolved_symbol,
            result
         );
      }


      if(
         !IsPositionAction(
            mission.action
         )
         &&
         !IsPendingAction(
            mission.action
         )
      )
      {
         FailResult(
            result,
            "Unsupported control action."
         );

         return result;
      }


      result.success = (
         result.failed_item_count
         == 0
      );


      if(
         result.success
      )
      {
         result.failure_reason = "";
      }


      return result;
   }
};


#endif