"""Traffic-class to priority mapping."""

from mlp.pdu import PRIO_CONTROL, PRIO_CURSOR, PRIO_MEDIA, PRIO_REFRESH, PRIO_REPORT


class QosTier:
    BACKGROUND = 0
    BEST_EFFORT = 1
    INTERACTIVE = 2
    REALTIME = 3

    _PRIO = {BACKGROUND: PRIO_REFRESH, BEST_EFFORT: PRIO_MEDIA,
             INTERACTIVE: PRIO_CURSOR, REALTIME: PRIO_REPORT}
    _WEIGHT = {BACKGROUND: 1, BEST_EFFORT: 2, INTERACTIVE: 4, REALTIME: 8}

    @staticmethod
    def mlp_priority(tier):
        return QosTier._PRIO[tier]

    @staticmethod
    def weight(tier):
        return QosTier._WEIGHT[tier]
