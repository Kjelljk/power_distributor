# Power Distributor: Sharing Power, Simply and Fairly

The Power Distributor is a smart program designed to manage how multiple units share the available electrical power in a building.

Its primary goal is to provide fair distribution of power in your home:

Limit Maximum Loads: It ensures you never draw more power than your main electrical supply is designed for, preventing triped fuses.

Ensure Fair Distribution: It automatically balances the power for each unit so that all get their fair share.

## How the Program Works

Think of the Power Distributor as a dedicated traffic cop for your electricity. It constantly watches the total amount of power being used by all units.

**1. The Safety Rules (Limits)**

The system is given two critical limits to follow:

* **System Hard Limit (X):** This is the maximum total power your entire installation can safely use at any time. This is the absolute stop sign for combined usage.

* **Individual Hard Cap (Y):** This is the maximum power any single unit is allowed to draw.

**2. Fair Distribution (The Sharing Principle)**

When the total power usage gets close to the System Hard Limit (X), the Distributor steps in to share the capacity fairly among all demanding appliances.

It applies a principle of proportional fairness:

* **Needs-Based Sharing:** If Charger A needs 10 kW and Water Heater B needs 5 kW (a 2:1 ratio of need), the system maintains that ratio. If only 3 kW of power is left, Charger A gets roughly 2 kW and Water Heater B gets 1 kW.

* **Progress for All:** This method ensures that even when power is scarce, every connected appliance continues to draw some energy and make progress toward its goal, rather than having some devices run at full power while others are completely shut down.

## The Overload Acceptance (OA) Feature

This is the system's most powerful feature for maximizing efficiency without sacrificing safety.

Electrical systems are often built with a margin of tolerance for very brief power spikes (like when a device first powers up). The OA feature uses this tolerance intelligently.

The Distributor acts with "patience" when a spike occurs:

* **Patience for Small Spikes:** If the combined power slightly exceeds the hard limit (e.g., by 5%), the Distributor will tolerate it for a short, set amount of time (e.g., several minutes). This often allows the temporary spike to subside on its own.

* **Rapid Response for Large Spikes:** If the power significantly exceeds the limit (e.g., by 20%), the Distributor allows it for only a very short duration (e.g., 30 seconds). If the power hasn't dropped by then, the system quickly and gradually reduces the power supplied to the individual unit until the total usage is back below the safe limit.

**The result?** Your appliances get to run at the highest possible power level, maximizing performance and speeding up tasks like EV charging, all while the Distributor make sure that the continuous safety of your electrical infrastructure.
