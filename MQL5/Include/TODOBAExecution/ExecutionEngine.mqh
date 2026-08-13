#ifndef TODOBA_EXECUTION_ENGINE_MQH
#define TODOBA_EXECUTION_ENGINE_MQH


#include <Trade/Trade.mqh>
#include <TODOBAExecution/ExecutionResult.mqh>
#include <TODOBAExecution/SymbolMapper.mqh>

class TODOBAExecutionEngine
{

private:

   CTrade trade;


   TODOBAExecutionResult BuildResult()
   {
      TODOBAExecutionResult result;

      result.success =
         trade.ResultRetcode()
         == TRADE_RETCODE_DONE;


      result.order_ticket =
         trade.ResultOrder();


      result.deal_ticket =
         trade.ResultDeal();


      result.retcode =
         trade.ResultRetcode();


      result.price =
         trade.ResultPrice();


      result.comment =
         trade.ResultComment();


      return result;
   }


public:

   TODOBAExecutionResult Execute(
      string symbol,
      string order_type,
      double volume,
      double entry,
      double sl,
      double tp,
      long magic_number,
      string comment
   )
   {

     trade.SetExpertMagicNumber(
   magic_number
);
symbol = TODOBA_SymbolMapper::Resolve(
   symbol
);

Print(
   "AFTER MAPPER SYMBOL=[",
   symbol,
   "]"
);

trade.SetTypeFilling(
   ORDER_FILLING_IOC
);
      trade.SetTypeFilling(
   ORDER_FILLING_IOC
);
Print(
   "TODOBA Engine order_type=[",
   order_type,
   "]"
);
      if(
         order_type == "BUY" ||
         order_type == "BUY NOW"
      )
      {Print(
   "TODOBA Engine: ENTER BUY BLOCK"
);
         Print(
            "TODOBA Engine: sending BUY ",
            symbol,
            " volume=",
            volume
         );


         trade.Buy(
            volume,
            symbol,
            0,
            sl,
            tp,
            comment
         );


         Print(
            "TODOBA Engine: BUY returned retcode=",
            trade.ResultRetcode(),
            " comment=",
            trade.ResultComment()
         );


         return BuildResult();
      }


            if(
         order_type == "SELL" ||
         order_type == "SELL NOW"
      )
      {
         Print(
            "TODOBA Engine: sending SELL ",
            symbol,
            " volume=",
            volume
         );


         trade.Sell(
            volume,
            symbol,
            0,
            sl,
            tp,
            comment
         );


         Print(
            "TODOBA Engine: SELL returned retcode=",
            trade.ResultRetcode(),
            " comment=",
            trade.ResultComment()
         );


         return BuildResult();
      }


      if(
         order_type == "BUY LIMIT"
      )
      {
         trade.BuyLimit(
            volume,
            entry,
            symbol,
            sl,
            tp,
            ORDER_TIME_GTC,
            0,
            comment
         );

         return BuildResult();
      }


      if(
         order_type == "SELL LIMIT"
      )
      {
         trade.SellLimit(
            volume,
            entry,
            symbol,
            sl,
            tp,
            ORDER_TIME_GTC,
            0,
            comment
         );

         return BuildResult();
      }


      if(
         order_type == "BUY STOP"
      )
      {
         trade.BuyStop(
            volume,
            entry,
            symbol,
            sl,
            tp,
            ORDER_TIME_GTC,
            0,
            comment
         );

         return BuildResult();
      }


      if(
         order_type == "SELL STOP"
      )
      {
         trade.SellStop(
            volume,
            entry,
            symbol,
            sl,
            tp,
            ORDER_TIME_GTC,
            0,
            comment
         );

         return BuildResult();
      }


      TODOBAExecutionResult failed;

      failed.success = false;
      failed.order_ticket = 0;
      failed.deal_ticket = 0;
      failed.retcode = 0;
      failed.price = 0;
      failed.comment = "Unsupported order type.";

      return failed;
   }

};


#endif