const { createApp, ref, reactive, h, onMounted, onUnmounted, computed, nextTick } = Vue
const { NButton, NSpace, NTag, NInput, NPopconfirm, NDropdown, NConfigProvider, NMessageProvider, NEmpty, NSpin, NCard, NForm, NFormItem, NModal, NLoadingBar, NDialog, NNotification, createDiscreteApi } = naive

/**
 * 创建全局消息和通知 API
 */
const { message, notification, loadingBar, dialog } = createDiscreteApi(
    ['message', 'notification', 'loadingBar', 'dialog'],
    {
        configProviderProps: {
            theme: 'light'
        }
    }
)

/**
 * 工具函数集
 */
const utils = {
    /**
     * 节流函数 - 限制函数调用频率
     * @param {Function} fn 要执行的函数
     * @param {number} delay 延迟时间(ms)
     * @returns {Function} 节流后的函数
     */
    throttle(fn, delay) {
        let lastExecuteTime = 0
        return function (...args) {
            const currentTime = Date.now()
            if (currentTime - lastExecuteTime >= delay) {
                fn.apply(this, args)
                lastExecuteTime = currentTime
            }
        }
    },
    
    /**
     * 防抖函数 - 合并短时间内的多次调用
     * @param {Function} fn 要执行的函数
     * @param {number} delay 延迟时间(ms)
     * @returns {Function} 防抖后的函数
     */
    debounce(fn, delay) {
        let timeoutId = null
        return function (...args) {
            if (timeoutId) clearTimeout(timeoutId)
            timeoutId = setTimeout(() => {
                fn.apply(this, args)
            }, delay)
        }
    }
}

const app = createApp({
    setup() {
        // 状态定义
        const accounts = ref([])
        const addDialogVisible = ref(false)
        const newAccount = ref({
            username: '',
            password: ''
        })
        const contextMenu = reactive({
            visible: false,
            x: 0,
            y: 0,
            row: null
        })

        // 加载状态
        const loading = ref(false)
        const loadingMessage = ref('')
        const refreshTimer = ref(null)

        // 表单提交状态
        const isSubmitting = ref(false)
        const formRef = ref(null)
        const formRules = {
            username: [
                { required: true, message: '请输入账号' },
                { min: 3, message: '账号长度不能小于3' }
            ],
            password: [
                { required: true, message: '请输入密码' },
                { min: 6, message: '密码长度不能小于6' }
            ]
        }

        // 确认对话框状态
        const confirmDialog = reactive({
            visible: false,
            title: '',
            message: '',
            type: 'warning',
            tag: '',
            loading: false,
            callback: null
        })

        /**
         * 表格列定义
         */
        const columns = [  // 改名:columns -> columns
            {
                title: '账号',
                key: 'username',
                width: 130,
                ellipsis: true,
                render(account) {  // 改名:row -> account
                    return h('div', {
                        class: 'username-cell',
                    }, [
                        // 账号状态图标
                        account.can_quick_switch 
                            ? h('div', {
                                class: 'quick-switch-icon',
                                title: '支持快速切换',
                                style: {
                                    display: 'inline-block !important',
                                    visibility: 'visible',
                                    marginRight: '4px'
                                }
                            })
                            : h('div', {
                                class: 'locked-icon',
                                title: '需要密码登录',
                                style: {
                                    display: 'inline-block !important',
                                    visibility: 'visible',
                                    marginRight: '4px'
                                }
                            }),
                        h('span', {}, account.username)
                    ])
                }
            },
            {
                title: '游戏ID',
                key: 'game_id',
                width: 180,
                render(row, index) {
                    // 为每行创建一个唯一的编辑状态
                    const rowKey = `${row.username}-${index}`
                    if (!app.editingStates) {
                        app.editingStates = {}
                    }
                    if (!app.editingValues) {
                        app.editingValues = {}
                    }
                    if (!app.editingStates[rowKey]) {
                        app.editingStates[rowKey] = ref(false)
                        app.editingValues[rowKey] = ref(row.game_id || '')
                    }
                    const isEditing = app.editingStates[rowKey]
                    const inputValue = app.editingValues[rowKey]

                    return h('div', {
                        class: 'game-id-cell',
                    }, [
                        isEditing.value
                            ? h(NInput, {
                                value: inputValue.value,
                                onUpdateValue: (v) => {
                                    inputValue.value = v
                                },
                                onBlur: () => {
                                    // 失去焦点时保存并关闭编辑状态
                                    isEditing.value = false
                                    if (inputValue.value !== row.game_id) {
                                        handleGameIdChange(row, inputValue.value)
                                    }
                                },
                                onKeydown: (e) => {
                                    e.stopPropagation()
                                    if (e.key === 'Enter') {
                                        e.target.blur()  // 触发 onBlur
                                    } else if (e.key === 'Escape') {
                                        inputValue.value = row.game_id || ''
                                        isEditing.value = false
                                    }
                                },
                                size: 'small',
                                style: {
                                    width: '150px',
                                    margin: '0'
                                },
                                autofocus: true,  // 自动获取焦点
                                'focus-after-mouse-enter': true  // 鼠标进入后自动聚焦
                            })
                            : h('div', {
                                class: 'game-id-text',
                                onClick: (e) => {
                                    e.preventDefault()
                                    e.stopPropagation()
                                    inputValue.value = row.game_id || ''
                                    isEditing.value = true
                                }
                            }, row.game_id || '点击编辑')
                    ])
                }
            },
            {
                title: '上次登录',
                key: 'last_login',
                width: 150,
                render(row) {
                    return h('span', {}, row.last_login || '从未登录')
                }
            },
            {
                title: '状态',
                key: 'status',
                width: 120,
                render(row) {
                    let type = 'default'
                    let text = row.status
                    
                    if (row.status === '正常') {
                        type = 'success'
                    } else if (row.status === '已解封') {
                        type = 'info'
                        text = '已解封'
                    } else if (row.status.includes('登录失败')) {
                        type = 'error'
                        text = '登录失败'
                    } else {
                        type = 'warning'  // 封禁时间
                    }
                    
                    return h(NTag, {
                        type: type,
                        style: row.status === '已解封' ? 'background-color: #2080f0; color: white;' : ''
                    }, { default: () => text })
                }
            },
            {
                title: '操作',
                key: 'actions',
                width: 140,
                render(row) {
                    return h(NSpace, {}, {
                        default: () => [
                            h(NDropdown, {
                                trigger: 'click',
                                options: [
                                    { label: '1天', key: 1 },
                                    { label: '3天', key: 3 },
                                    { label: '7天', key: 7 },
                                    { label: '30天', key: 30 }
                                ],
                                onSelect: (days) => handleBan(row, days)
                            }, {
                                default: () => h(NButton, {
                                    size: 'small',
                                    type: row.status === '正常' ? 'primary' : 'warning'
                                }, { default: () => row.status === '正常' ? '封' : '改' })
                            }),
                            h(NPopconfirm, {
                                onPositiveClick: () => handleDelete(row)
                            }, {
                                trigger: () => h(NButton, {
                                    size: 'small',
                                    type: 'error'
                                }, { default: () => '删' }),
                                default: () => '确定要删除这个账号吗？'
                            })
                        ]
                    })
                }
            }
        ]

        // 添加 rowProps 配置
        const rowProps = (row) => {
            return {
                style: row.isLoggingIn ? 'cursor: wait; opacity: 0.7;' : 'cursor: pointer',
                onClick: () => {
                    // 可以添加单击行为如果需要
                },
                onDblclick: (e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    if (row.isLoggingIn) {
                        return
                    }
                    console.log('双击登录数据:', row)
                    handleLogin(row)
                },
                onContextmenu: (e) => handleContextMenu(row, e)
            }
        }

        /**
         * 显示通知消息
         * @param {string} type 通知类型: success|warning|error|info
         * @param {string} title 通知标题
         * @param {string} content 通知内容
         */
        const showNotification = (type, title, content) => {
            notification[type]({
                title,
                content,
                duration: 3000,
                keepAliveOnHover: true,
                closable: true
            })
        }

        /**
         * 加载账号列表(带防抖)
         * @param {boolean} isInitialLoad 是否为首次加载
         */
        const loadAccountList = utils.debounce(async (isInitialLoad = false) => {
            if (loading.value) return
            
            try {
                loading.value = true
                const response = await fetch('/api/accounts')
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`)
                }
                const data = await response.json()
                
                if (data.status === 'error') {
                    message.error(data.message || '加载失败')
                    return
                }
                
                accounts.value = data.accounts || []
                
                // 检查解封通知
                if (isInitialLoad && data.unbanned?.length > 0) {
                    notification.success({
                        title: '账号解封提醒',
                        content: data.unbanned.length === 1
                            ? `账号 ${data.unbanned[0]} 已解除封禁`
                            : `${data.unbanned.length}个账号已解除封禁：\n${data.unbanned.join(', ')}`,
                        duration: 5000
                    })
                }
            } catch (error) {
                console.error('加载失败:', error)
                message.error('加载失败，请检查网络连接')
            } finally {
                loading.value = false
            }
        }, 300)

        /**
         * 自动刷新相关函数
         */
        const throttledRefresh = utils.throttle(() => {
            loadAccountList(false)
        }, 5000)
        
        const startAutoRefresh = () => {
            stopAutoRefresh()
            refreshTimer.value = setInterval(() => {
                loadAccountList(false)
            }, 30000) // 30秒刷新一次
        }
        
        const stopAutoRefresh = () => {
            if (refreshTimer.value) {
                clearInterval(refreshTimer.value)
                refreshTimer.value = null
            }
        }

        /**
         * 处理账号登录
         * @param {Object} account 账号信息
         */
        const handleAccountLogin = async (account) => {
            try {
                stopAutoRefresh()
                
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(account)
                })
                
                const data = await response.json()
                
                if (!response.ok) {
                    handleLoginError(data)
                    return
                }

                if (data.refresh) {
                    await loadAccountList()
                }
                message.success('登录成功')
                
            } catch (error) {
                message.error('网络请求失败，请重试')
            } finally {
                startAutoRefresh()
            }
        }

        /**
         * 处理登录错误
         * @param {Object} errorData 错误数据
         */
        const handleLoginError = (errorData) => {
            switch(errorData.code) {
                case 2000:
                    message.error('未找到Steam客户端，请检查安装')
                    break
                case 2001:
                    message.error('Steam启动失败，请检查进程')
                    break
                case 3002:
                    message.error('密码错误，请重试')
                    break
                default:
                    message.error(errorData.message || '登录失败')
            }
        }

        const handleAdd = async () => {
            if (!newAccount.value.username || !newAccount.value.password) {
                message.warning('账号和密码不能为空');
                return;
            }

            try {
                const isEdit = accounts.value.some(acc => acc.username === newAccount.value.username);
                message.loading(isEdit ? '正在更新账号...' : '正在添加账号...', 1);

                if (isEdit) {
                    // 更新现有账号
                    const index = accounts.value.findIndex(acc => acc.username === newAccount.value.username);
                    accounts.value[index] = { ...accounts.value[index], ...newAccount.value };
                } else {
                    // 添加新账号
                    await fetch('/api/accounts', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(newAccount.value)
                    });
                }
                
                addDialogVisible.value = false;
                newAccount.value = { username: '', password: '' };
                await loadAccountList();
                message.success(isEdit ? '账号已更新' : '账号添加成功');
            } catch (error) {
                message.error(isEdit ? '更新失败，请重试' : '添加失败，请重试');
            }
        }

        const handleDelete = async (account) => {
            showConfirmDialog({
                title: '删除账号',
                message: `确定要删除账号 ${account.username} 吗？此操作不可恢复！`,
                type: 'error',
                tag: '危险',
                callback: async () => {
                    try {
                        await API.deleteAccount(account.username)
                        message.success('账号已删除')
                        await loadAccountList()
                    } catch (error) {
                        message.error('删除失败，请重试')
                    }
                }
            })
        }

        const handleBan = async (account, days) => {
            showConfirmDialog({
                title: '封禁账号',
                message: `确定要封禁账号 ${account.username} ${days}天吗？`,
                type: 'warning',
                tag: '警告',
                callback: async () => {
                    try {
                        await API.setBanTime(account.username, days)
                        message.success('设置成功')
                        await loadAccountList()
                    } catch (error) {
                        message.error('设置失败')
                    }
                }
            })
        }

        const handleGameIdChange = async (account, newValue) => {
            try {
                const response = await fetch(`/api/accounts/${account.username}/game_id`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ game_id: newValue })
                });
                
                if (!response.ok) {
                    throw new Error('保存失败');
                }
                
                account.game_id = newValue;
                message.success('游戏ID已更新');
            } catch (error) {
                message.error('保存失败，请重试');
                await loadAccountList();  // 出错时重新加载数据
            }
        }

        // 修改右键菜单选项
        const contextMenuOptions = computed(() => {
            const options = [
                {
                    label: '添加账号',
                    key: 'add',
                    icon: renderIcon('add')
                }
            ]
            
            if (contextMenu.row) {
                options.unshift(
                    {
                        label: '登录此账号',
                        key: 'login',
                        icon: renderIcon('login')
                    },
                    {
                        label: '编辑账号',
                        key: 'edit',
                        icon: renderIcon('edit')  // 需要添加编辑图标
                    }
                )
            }
            
            return options
        })

        // 修改右键菜单处理函数
        const handleContextMenuSelect = (key) => {
            switch (key) {
                case 'login':
                    if (contextMenu.row) {
                        handleAccountLogin({
                            username: contextMenu.row.username,
                            password: contextMenu.row.password
                        })
                    }
                    break
                case 'edit':
                    if (contextMenu.row) {
                        newAccount.value = { 
                            username: contextMenu.row.username,
                            password: contextMenu.row.password
                        }
                        addDialogVisible.value = true  // 复用添加账号的对话框
                    }
                    break
                case 'add':
                    showAddDialog()
                    break
            }
            contextMenu.visible = false
        }

        // 简单的图标渲染函数
        const renderIcon = (type) => {
            return () => h('div', { class: `menu-icon ${type}-icon` }, '')
        }

        // 修改 handleContextMenu 函数
        const handleContextMenu = (row, event) => {
            event.preventDefault()
            event.stopPropagation()
            
            contextMenu.visible = true
            contextMenu.x = event.clientX
            contextMenu.y = event.clientY
            contextMenu.row = row
        }

        const showAddDialog = () => {
            contextMenu.visible = false  // 关闭右键菜单
            addDialogVisible.value = true
            newAccount.value = { username: '', password: '' }  // 清空表单
        }

        // 修改容器右键菜单处理函数
        const handleContainerContextMenu = (event) => {
            // 阻止默认的浏览器右键菜单
            event.preventDefault()
            event.stopPropagation()
            
            // 显示只包含"添加账号"的右键菜单
            contextMenu.visible = true
            contextMenu.x = event.clientX
            contextMenu.y = event.clientY
            contextMenu.row = null  // 清空行信息，表示不是在行上点击
        }

        // 表单提交处理
        const handleSubmitForm = async () => {
            try {
                await formRef.value?.validate()
                isSubmitting.value = true
                await handleAdd()
            } catch (err) {
                // 表单验证失败
            } finally {
                isSubmitting.value = false
            }
        }

        // 显示确认对话框
        const showConfirmDialog = ({title, message, type = 'warning', tag = '警告', callback}) => {
            confirmDialog.title = title
            confirmDialog.message = message
            confirmDialog.type = type
            confirmDialog.tag = tag
            confirmDialog.callback = callback
            confirmDialog.visible = true
        }

        // 确认对话框回调
        const handleConfirm = async () => {
            if (confirmDialog.callback) {
                confirmDialog.loading = true
                try {
                    await confirmDialog.callback()
                    confirmDialog.visible = false
                } finally {
                    confirmDialog.loading = false
                }
            }
        }

        // 修改登录处理函数
        const handleLogin = async (row) => {
            // 设置登录状态
            row.isLoggingIn = true
            message.loading('正在登录...', 0)  // 持续显示，直到手动关闭
            
            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        username: row.username,
                        password: row.password,
                        remember_password: true
                    })
                })
                
                const data = await response.json()
                if (data.status === 'error') {
                    // 如果是密码登录超时，只显示简单提示
                    if (data.code === ErrorCode.STEAM_LOGIN_FAILED.code) {
                        message.error('登录失败')
                    } else {
                        // 其他错误显示详细信息
                        message.error(data.message || '登录失败')
                    }
                    message.destroyAll()  // 清除 loading 消息
                    return
                }
                
                message.destroyAll()  // 清除 loading 消息
                message.success('登录成功')
                if (data.refresh) {
                    await loadAccountList()
                }
            } catch (error) {
                console.error('登录失败:', error)
                message.destroyAll()  // 清除 loading 消息
                message.error('登录失败')
            } finally {
                // 清除登录状态
                row.isLoggingIn = false
            }
        }

        // 组件生命周期钩子
        onMounted(async () => {
            console.log('组件挂载，执行首次加载')
            
            // 阻止整个文档的默认右键菜单
            document.addEventListener('contextmenu', (event) => {
                event.preventDefault()
                const tableEl = event.target.closest('.n-data-table')
                if (!tableEl) {
                    handleContainerContextMenu(event)
                }
            })

            // 点击其他地方关闭菜单
            document.addEventListener('click', (event) => {
                if (!event.target.closest('.n-dropdown')) {
                    contextMenu.visible = false
                }
            })

            // 页面可见性变化处理
            document.addEventListener('visibilitychange', () => {
                if (document.hidden) {
                    stopAutoRefresh()
                } else {
                    loadAccountList()
                    startAutoRefresh()
                }
            })

            try {
                await loadAccountList(true)
                startAutoRefresh()
            } catch (error) {
                console.error('初始化失败:', error)
                message.error('初始化失败，请刷新页面重试')
            }
        })

        onUnmounted(() => {
            stopAutoRefresh()
            document.removeEventListener('visibilitychange', () => {})
        })

        // 确保所有API请求使用正确的前缀
        const API = {
            getAccounts: () => fetch('/api/accounts').then(r => r.json()),
            addAccount: (data) => fetch('/api/accounts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            }).then(r => r.json()),
            deleteAccount: (username) => fetch(`/api/accounts/${username}`, {
                method: 'DELETE'
            }).then(r => r.json()),
            setBanTime: (username, days) => fetch(`/api/accounts/${username}/ban`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ days })
            }).then(r => r.json()),
            updateGameId: (username, gameId) => fetch(`/api/accounts/${username}/game_id`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ game_id: gameId })
            }).then(r => r.json()),
            login: (username, password) => fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            }).then(r => r.json())
        }

        return {
            accounts,
            columns,
            addDialogVisible,
            newAccount,
            contextMenu,
            loading,
            loadingMessage,
            handleAccountLogin,
            handleAdd,
            handleDelete,
            handleBan,
            handleGameIdChange,
            handleContextMenu,
            showAddDialog,
            rowProps,
            contextMenuOptions,
            handleContextMenuSelect,
            handleContainerContextMenu,
            API,
            isSubmitting,
            formRef,
            formRules,
            confirmDialog,
            handleSubmitForm,
            showConfirmDialog,
            handleConfirm
        }
    }
})

// 注册 Naive UI 组件
app.use(naive)
app.mount('#app') 