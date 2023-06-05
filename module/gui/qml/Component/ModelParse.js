.pragma library


//
//*****************************请注意下面的函数只适用与pydantic生成的task的参数
//

/**
 * 解析出group的数组，
 * @param {Object} data.properties
 * @returns {Array} 类似这样：[Device,Error,Optimization]
 */
function parseGroup(properties) {
    var result = []
    for(const key in properties){
        if(!('$ref' in properties[key])){
            continue
        }
        const value = properties[key]['$ref'];
        const lastPart = value.substring(value.lastIndexOf('/') + 1);
        result.push(lastPart)
    }
    return result
}

/**
 * 解析出group一一对应的的数组，
 * @param {Object} data.properties
 * @returns {Object} 类似这样：{"Device":"device", "Error":"error", "Optimization":"optimization"}
 */
function parseGroups(properties) {
    var result = {}
    for(const key in properties){
        if(!('$ref' in properties[key])){
            continue
        }
        const value = properties[key]['$ref'];
        const lastPart = value.substring(value.lastIndexOf('/') + 1);
        result[lastPart] = key
    }
    return result
}


/**
 * 解析ref的最后一个Name
 * @param {String} ref
 * @returns {String}
 */
function parseRef(ref){
    return ref.substring(ref.lastIndexOf('/') + 1)
}


/**
 * 解析出某个group的参数组，
 * @param {Object} definitions
 * @param {string} group
 * @returns {Array} -
 */
function parseArgument(definitions, group){
    if(!(group in definitions)){
        return null
    }
    const result = []
    const pro = definitions[group]["properties"]
    for(const key in pro){
        const arg = {}
        const argName = pro[key]

        arg["name"] = key

        if("title" in argName){
            arg["title"] = argName.title
        }else{

        }

        //如果有allOf表示这个配置字段是一个枚举的, 一般枚举的就是string
        if("allOf" in argName){
            const ref = argName.allOf[0]["$ref"]
            arg["title"] = parseRef(ref)
            arg["type"] = "enum"
        }

        if("description" in argName){
            arg["description"] = argName.description
        }else{
            // 没有帮助就没有帮助
        }

        if("default" in argName){
            arg["default"] = argName["default"]
        }else{
            console.error(arg["title"], 'have not default')
        }

        if("type" in argName){
            arg["type"] = argName.type
        }

        if(arg["type"] === "enum"){
            arg["options"] = definitions[arg.title]["enum"]
        }

        result.push(arg)

    }
    return result
}

/**
 * 合并某个group的参数组，
 * @param {Object} argument
 * @param {Object} values
 * @returns {Object} - 就是添加了value这个一个值
 */
function mergeArgument(argument, values){
    for(let key in argument){
        const name = argument[key].name
        if(name in values){
            argument[key]["value"] = values[name]
        }
    }
    return argument
}
