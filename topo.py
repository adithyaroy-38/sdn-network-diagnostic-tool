from mininet.topo import Topo


class DiamondTopo(Topo):
    r"""
    Four-switch diamond topology.

             s2 -------- s4
            /              \
        h1-s1                h2
            \              /
             s3 ---------

    h3 connects to s2
    h4 connects to s3
    """

    def build(self):

        # Create switches
        s1 = self.addSwitch('s1', protocols='OpenFlow13')
        s2 = self.addSwitch('s2', protocols='OpenFlow13')
        s3 = self.addSwitch('s3', protocols='OpenFlow13')
        s4 = self.addSwitch('s4', protocols='OpenFlow13')

        # Create hosts
        h1 = self.addHost('h1', ip='10.0.0.1/24')
        h2 = self.addHost('h2', ip='10.0.0.2/24')
        h3 = self.addHost('h3', ip='10.0.0.3/24')
        h4 = self.addHost('h4', ip='10.0.0.4/24')

        # Host-to-switch links
        self.addLink(h1, s1)
        self.addLink(h2, s4)
        self.addLink(h3, s2)
        self.addLink(h4, s3)

        # Diamond switch links with delays
        self.addLink(s1, s2, delay='5ms')
        self.addLink(s2, s4, delay='5ms')
        self.addLink(s1, s3, delay='20ms')
        self.addLink(s3, s4, delay='20ms')


topos = {
    'diamond': DiamondTopo
}
