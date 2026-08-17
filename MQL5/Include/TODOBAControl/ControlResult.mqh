#ifndef TODOBA_CONTROL_RESULT_MQH
#define TODOBA_CONTROL_RESULT_MQH


struct TODOBAControlResult
{
   bool success;

   int matched_position_count;
   int closed_position_count;

   int matched_pending_order_count;
   int canceled_pending_order_count;

   int failed_item_count;

   string failure_reason;
};


#endif