import switch
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub

from datetime import datetime

# class CollectTrainingStatsApp(simple_switch_13.SimpleSwitch13):
class CollectTrainingStatsApp(switch.SimpleSwitch13):
    def __init__(self, *args, **kwargs):
        super(CollectTrainingStatsApp, self).__init__(*args, **kwargs)
        #such as the switch ID, port numbers, capabilities, and other relevant information that the controller needs to manage the switch.
        self.datapaths = {}#store information about the switches that have been connected to the controller.
        self.monitor_thread = hub.spawn(self.monitor)#function that periodically sends requests to the switches connected to the Ryu controller to get flow statistics data,

        file0 = open("FlowStatsfile.csv","w")
        #word
        file0.write('timestamp,datapath_id,flow_id,ip_src,tp_src,ip_dst,tp_dst,ip_proto,icmp_code,icmp_type,flow_duration_sec,flow_duration_nsec,idle_timeout,hard_timeout,flags,packet_count,byte_count,packet_count_per_second,packet_count_per_nsecond,byte_count_per_second,byte_count_per_nsecond,label\n')
        file0.close()

    #Asynchronous message
    #المحول متصل بوحدة التحكم أم لا ==حدث
    #EventOFPStateChange يتم تشغيل هذا الحدث عندما تتغير حالة المحول المتصل بوحدة تحكم Ryu.
    @set_ev_cls(ofp_event.EventOFPStateChange,[MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change_handler(self, ev):#event object that contains information about the state change event. 
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:#المحول قد تم توصيله بوحدة التحكم
            if datapath.id not in self.datapaths:
                self.logger.debug('register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath#adds the `datapath` object to the `datapaths` dictionary

        elif ev.state == DEAD_DISPATCHER:#المحول قد تم قطع اتصاله بوحدة التحكم
            if datapath.id in self.datapaths:
                self.logger.debug('unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]#removes the `datapath` object from the `datapaths` dictionary.

#sends flow statistics requests to all switches in `datapaths` and sleeps for 10 seconds before sending the requests again.
    def monitor(self):
        while True:
            for dp in self.datapaths.values():
                self.request_stats(dp)
            hub.sleep(10)


    def request_stats(self, datapath):# sends a flow statistics request to a switch
        self.logger.debug('send stats request: %016x', datapath.id)
        
        parser = datapath.ofproto_parser

        req = parser.OFPFlowStatsRequest(datapath)#creates an `OFPFlowStatsRequest` message using the OpenFlow parser associated with the `datapath`.
        datapath.send_msg(req)# The message is then sent 
#مهم
#EventOFPFlowStatsReply` event is triggered whenever a switch responds to a flow statistics request. 
    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):

        timestamp = datetime.now()
        timestamp = timestamp.timestamp()
        icmp_code = -1
        icmp_type = -1
        tp_src = 0
        tp_dst = 0

        file0 = open("FlowStatsfile.csv","a+")
        body = ev.msg.body
        for stat in sorted([flow for flow in body if (flow.priority == 1) ], key=lambda flow:
            (flow.match['eth_type'],flow.match['ipv4_src'],flow.match['ipv4_dst'],flow.match['ip_proto'])):
        

            ip_src = stat.match['ipv4_src']
            ip_dst = stat.match['ipv4_dst']
            ip_proto = stat.match['ip_proto']
            
            if stat.match['ip_proto'] == 1:#icmp
                icmp_code = stat.match['icmpv4_code']
                icmp_type = stat.match['icmpv4_type']

            elif stat.match['ip_proto'] == 6:#tcp
                tp_src = stat.match['tcp_src']
                tp_dst = stat.match['tcp_dst']

            elif stat.match['ip_proto'] == 17:#udp
                tp_src = stat.match['udp_src']
                tp_dst = stat.match['udp_dst']

            flow_id = str(ip_src) + str(tp_src) + str(ip_dst) + str(tp_dst) + str(ip_proto)
            #حساب البارمترات الاخرى
            try:
                packet_count_per_second = stat.packet_count/stat.duration_sec
                packet_count_per_nsecond = stat.packet_count/stat.duration_nsec
            except:
                packet_count_per_second = 0
                packet_count_per_nsecond = 0
                
            try:
                byte_count_per_second = stat.byte_count/stat.duration_sec
                byte_count_per_nsecond = stat.byte_count/stat.duration_nsec
            except:
                byte_count_per_second = 0
                byte_count_per_nsecond = 0
                

            file0.write("{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\n"
                .format(timestamp, ev.msg.datapath.id, flow_id, ip_src, tp_src,ip_dst, tp_dst,
                        stat.match['ip_proto'],icmp_code,icmp_type,
                        stat.duration_sec, stat.duration_nsec,
                        stat.idle_timeout, stat.hard_timeout,
                        stat.flags, stat.packet_count,stat.byte_count,
                        packet_count_per_second,packet_count_per_nsecond,
                        byte_count_per_second,byte_count_per_nsecond,0))
        file0.close()