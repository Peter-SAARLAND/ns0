import docker


class Docker:
    """Docker"""

    def __init__(self):
        self.client = docker.from_env()

    def getRecords(self):
        """Function description."""
        # Creating a Set here instead of a list to promote deduplication
        records = []

        for container in self.client.containers.list():
            container_labels = []

            # Check if container qualifies as ns0 backend
            for label in container.labels:
                if label.lower().startswith("ns0"):
                    container_labels.append(label)

            # Container contains labels that are relevant for us
            if len(container_labels) > 0:
                # Parse labels to Records
                records = {}

                # Example Labels:
                # ns0.traefik.hostname=proxy.ns0.co
                # ns0.traefik.endpoints=public
                for label in container_labels:
                    # Split label into list, remove first item (removes "ns0").
                    #
                    # Example Labels:
                    # traefik.hostname -> ["traefik","hostname"]
                    # traefik.endpoints -> ["traefik","endpoint"]
                    label_as_list = label.split(".")[1:]

                    # First item in list is record_name
                    # It's an arbitrary namespace used to enable overloading
                    # container labels
                    #
                    # Example Labels:
                    # traefik
                    # traefik
                    record_name = label_as_list[0]

                    # Remove first item (record_name) from list
                    #
                    # Example Labels:
                    # hostname -> ["hostname"]
                    # endpoints -> ["endpoints"]
                    label_as_list.pop(0)

                    # Parse the rest of the label as keys
                    # We assume that there's only 1 more item left
                    #
                    # Example Labels:
                    # hostname - key=hostname
                    # endpoints - key=endpoints
                    key = label_as_list[0]

                    # Get the labels value from the Containers labels
                    #
                    # Example Labels:
                    # ns0.traefik.hostname - value=proxy.ns0.co
                    # ns0.traefik.endpoints - value=public
                    value = container.labels[label]
                    if key == "endpoints":
                        value = value.split(",")

                    # If we haven't already parsed this frontend, create empty key
                    if record_name not in records:
                        records[record_name] = {}

                    # Set Record
                    records[record_name][key] = value

                    # Source
                    source = {"name": "docker", "type": "container", "id": container.id}

                    if "sources" not in records[record_name]:
                        records[record_name]["sources"] = []

                    invalid = False
                    for e_source in records[record_name]["sources"]:

                        if (
                            e_source["id"] == source["id"]
                            and e_source["type"] == source["type"]
                        ):
                            invalid = True

                    if not invalid:
                        records[record_name]["sources"].append(source)

                return records
