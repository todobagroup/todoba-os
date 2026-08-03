#ifndef TODOBA_EXECUTION_RESULT_MQH
#define TODOBA_EXECUTION_RESULT_MQH


struct TODOBAExecutionResult
{
   bool success;

   long order_ticket;

   long deal_ticket;

   uint retcode;

   double price;

   string comment;
};


#endif